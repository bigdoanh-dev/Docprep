"""Shared FIFO dispatch and non-expiring model slots. PostgreSQL is recovery authority."""
import json
import uuid
import redis
from app.errors import ApiError

CLAIM = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return nil end
if redis.call('ZCARD', KEYS[3]) >= tonumber(ARGV[3]) then return nil end
local first = redis.call('ZRANGE', KEYS[2], 0, 0)
if #first == 0 then return nil end
redis.call('ZREM', KEYS[2], first[1])
redis.call('ZADD', KEYS[3], ARGV[2], first[1])
return first[1]
"""
ENQUEUE = """
if redis.call('ZSCORE', KEYS[2], ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], 'NX', ARGV[2], ARGV[1])
redis.call('SET', KEYS[3], ARGV[1])
return 1
"""
RELEASE = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
if redis.call('GET', KEYS[3]) == ARGV[1] then redis.call('DEL', KEYS[3]) end
return 1
"""
SLOT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
if redis.call('HLEN', KEYS[2]) >= tonumber(ARGV[3]) then return 0 end
redis.call('HSET', KEYS[2], ARGV[2], ARGV[4])
return 1
"""


class Admission:
    def __init__(self, cfg):
        self.cfg = cfg
        self.r = redis.Redis.from_url(cfg.redis_url, decode_responses=True,
                                     socket_connect_timeout=2, socket_timeout=3)
        self.p = cfg.namespace + ":"
        self.claim_script = self.r.register_script(CLAIM)
        self.enqueue_script = self.r.register_script(ENQUEUE)
        self.release_script = self.r.register_script(RELEASE)
        self.slot_script = self.r.register_script(SLOT)

    def key(self, name):
        return self.p + name

    def learner_key(self, turn):
        owner = turn['learner_id'] if turn['learner_id'] is not None else 'system:' + str(turn['id'])
        return self.key(f'learner:{owner}')

    def epoch(self):
        return self.r.get(self.key("epoch"))

    def ready(self):
        epoch = self.epoch()
        return bool(epoch and self.r.get(self.key("ready")) == epoch)

    def require_ready(self):
        try:
            if self.ready():
                return
        except redis.RedisError:
            pass
        raise ApiError(503, "ai_unavailable", "Bộ điều phối AI chưa sẵn sàng. Vui lòng thử lại.")

    def enqueue(self, turn):
        self.enqueue_script(keys=[self.key("queue"), self.key("processing"),
                                  self.learner_key(turn)],
                            args=[str(turn["id"]), turn["seq"]])

    def claim(self, epoch, now):
        return self.claim_script(keys=[self.key("ready"), self.key("queue"), self.key("processing")],
                                 args=[epoch, now, self.cfg.active])

    def release(self, turn):
        self.release_script(keys=[self.key("queue"), self.key("processing"),
                                  self.learner_key(turn)], args=[str(turn["id"])])

    def slot(self, resource, call_id, owner):
        return bool(self.slot_script(keys=[self.key("ready"), self.key("slots:" + resource)],
                                     args=[self.epoch() or "", str(call_id), self.cfg.model_limit, owner]))

    def release_slot(self, resource, call_id):
        self.r.hdel(self.key("slots:" + resource), str(call_id))

    def emit(self, turn_id, event, data):
        if event == "status":
            data = {**data, "turn_id": str(turn_id)}
        key = self.key(f"events:{turn_id}")
        pipe = self.r.pipeline()
        pipe.xadd(key, {"event": event, "data": json.dumps(data, ensure_ascii=False)}, maxlen=512)
        pipe.expire(key, self.cfg.event_ttl_s)
        return pipe.execute()[0]

    def purge(self, turn_id):
        self.r.delete(self.key(f"events:{turn_id}"))

    def reset(self):
        """Caller holds the cross-process PostgreSQL recovery lock."""
        epoch = str(uuid.uuid4())
        self.r.delete(self.key("ready"))
        # Dispatch state only; retained events have their own TTL and cursor rules.
        keys = [self.key("queue"), self.key("processing")]
        keys += list(self.r.scan_iter(match=self.key("learner:*")))
        keys += list(self.r.scan_iter(match=self.key("slots:*")))
        if keys:
            self.r.delete(*keys)
        self.r.set(self.key("epoch"), epoch)
        return epoch

    def close(self):
        self.r.close()
