"""Content-team runtime: separate DB, tokens, OpenAPI and origin. No learner/model imports."""
import os
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID
from fastapi import FastAPI, Depends, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from starlette.exceptions import HTTPException
from app.errors import ApiError, api_error_handler, http_error_handler, validation_error_handler, unexpected_error_handler
from app.content import auth, service
from app.content.db import validate_url, check_ready
from app.content.importer import asset_root


class SafeRoute(APIRoute):
    def get_route_handler(self):
        handler=super().get_route_handler()
        async def safe(request):
            try:return await handler(request)
            except (ApiError,RequestValidationError,HTTPException):raise
            except Exception as exc:
                import logging
                logging.getLogger('content').warning('content_request_failed',extra={'error_type':type(exc).__name__})
                raise ApiError(503,'content_unavailable','Kho tài liệu tạm thời chưa sẵn sàng. Hãy tải lại hoặc liên hệ người vận hành.') from None
        return safe


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(Input):
    username: str = Field(min_length=1,max_length=64)
    password: str = Field(min_length=1,max_length=1024)


class Refresh(Input):
    refresh_token: str = Field(min_length=1,max_length=256)


class Issue(Input):
    id: int
    primary: bool
    conf: float | None = Field(default=None,ge=0,le=1)


class Domain(Input):
    id: str = Field(max_length=20)
    conf: float | None = Field(default=None,ge=0,le=1)


class Bloom(Input):
    level: Literal['Nhớ','Hiểu','Áp dụng','Phân tích','Đánh giá']
    conf: float | None = Field(default=None,ge=0,le=1)


class Tags(Input):
    van_de: list[Issue] = Field(min_length=1,max_length=3)
    mien: list[Domain] = Field(min_length=1,max_length=2)
    bloom_ceiling: Bloom
    content_type: str = Field(max_length=50)
    population: list[str] = Field(default_factory=list,max_length=3)
    ly_do: str = Field(default='',max_length=6000)


class Proposal(Input):
    row_version: int = Field(ge=1)
    taxonomy_version: str = Field(max_length=100)
    tags: Tags


class Decision(Input):
    row_version: int = Field(ge=1)
    purpose: Literal['classification','content']
    decision: Literal['accept','revise','reject']
    comment: str = Field(min_length=1,max_length=4000)


class ReleaseInput(Input):
    version: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$')
    chunk_ids: list[UUID] = Field(min_length=1,max_length=5000)


class ErrorDetail(BaseModel):
    code: str
    message_vi: str
    details: dict | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


def create_app(database_url=None):
    @asynccontextmanager
    async def lifespan(app):
        url=validate_url(database_url or os.environ['CONTENT_DATABASE_URL'])
        pool=ConnectionPool(url,min_size=1,max_size=5,kwargs={'row_factory':dict_row},open=False)
        pool.open(wait=True,timeout=10)
        try:
            with pool.connection() as conn:check_ready(conn)
            app.state.pool=pool
            yield
        finally:pool.close()

    app=FastAPI(title='YHDP Content Workspace',version='1.0.0',lifespan=lifespan,
        responses={status:{'model':ErrorEnvelope} for status in (401,403,404,409,422,429,500,503)})
    app.router.route_class=SafeRoute
    app.add_exception_handler(ApiError,api_error_handler)
    app.add_exception_handler(RequestValidationError,validation_error_handler)
    app.add_exception_handler(HTTPException,http_error_handler)
    app.add_exception_handler(Exception,unexpected_error_handler)

    def connection(request: Request):
        with request.app.state.pool.connection() as conn:yield conn

    Conn=Annotated[object,Depends(connection)]

    bearer=HTTPBearer(auto_error=False,scheme_name='ContentAccessToken')

    def principal(conn: Conn,token: Annotated[HTTPAuthorizationCredentials | None,Depends(bearer)]):
        if not token:raise ApiError(401,'unauthenticated','Bạn cần đăng nhập vào kho tài liệu.')
        return auth.authenticate(conn,token.credentials)

    User=Annotated[dict,Depends(principal)]

    @app.get('/health')
    def health():return {'ok':True,'service':'content','model_provider':'disabled'}

    @app.get('/readyz')
    def ready(conn: Conn):
        check_ready(conn)
        return {'ok':True}

    @app.post('/v1/auth/login')
    def login(body: Login,request: Request,conn: Conn):
        return auth.login(conn,body.username,body.password,request.client.host if request.client else 'local')

    @app.post('/v1/auth/refresh')
    def refresh(body: Refresh,conn: Conn):
        # Lock the subject before the refresh row, matching CLI reset lock ordering.
        token=conn.execute('select user_id from content_token where hash=%s',(auth.digest(body.refresh_token),)).fetchone()
        if not token:raise ApiError(401,'unauthenticated','Phiên đăng nhập không hợp lệ.')
        user=conn.execute('select * from content_user where id=%s for update',(token['user_id'],)).fetchone()
        t=conn.execute("select * from content_token where hash=%s and kind='refresh' and not revoked and expires_at>now() for update",(auth.digest(body.refresh_token),)).fetchone()
        if not t or not user['active']:raise ApiError(401,'unauthenticated','Phiên đăng nhập không hợp lệ.')
        conn.execute('update content_token set revoked=true where family=%s',(t['family'],))
        return auth.issue(conn,user,t['family'])

    @app.post('/v1/auth/logout')
    def logout(user: User,conn: Conn):
        conn.execute('update content_token set revoked=true where family=%s',(user['family'],))
        return {'ok':True}

    @app.get('/v1/me')
    def me(user: User):return {k:user[k] for k in ('id','username','display_name','roles')}

    @app.get('/v1/documents')
    def documents(user: User,conn: Conn):
        return {'items':conn.execute('''select d.*,r.id revision_id,r.revision_no,r.source_availability,
            (select count(*) from document_chunk c where c.revision_id=r.id) chunks
            from source_document d left join lateral(select * from source_document_revision where document_id=d.id
            order by revision_no desc limit 1) r on true order by d.external_doc_id''').fetchall()}

    @app.get('/v1/documents/{document_id}/revisions')
    def revisions(document_id: UUID,user: User,conn: Conn):
        return {'items':conn.execute('select * from source_document_revision where document_id=%s order by revision_no desc',(document_id,)).fetchall()}

    @app.get('/v1/taxonomies')
    def taxonomies(user: User,conn: Conn):
        return {'items':conn.execute('select * from taxonomy_snapshot order by version').fetchall(),
                'content_types':service.TYPES,'populations':service.POPULATIONS,'bloom':service.BLOOM}

    policy_fields={name:{'type':['string','null'],'description':'Effective decision policy: human-v1 or temporary source-baseline-v1; null if not accepted.'}
                   for name in ('classification_policy','content_policy')}
    @app.get('/v1/chunks',responses={200:{'description':'Paginated chunks and their effective acceptance policy.',
        'content':{'application/json':{'schema':{'type':'object','properties':{'items':{'type':'array',
            'items':{'type':'object','properties':policy_fields}}}}}}}})
    def chunks(user: User,conn: Conn,classification: Literal['classified','unclassified'] | None=None,
               document: str | None=None,issue: int | None=None,reason: str | None=None,
               revision_id: UUID | None=None,offset: int=0,limit: int=25):
        if offset<0 or not 1<=limit<=100:raise ApiError(422,'invalid_request','Phân trang không hợp lệ.')
        where=['true'];params=[]
        if revision_id:where.append('c.revision_id=%s');params.append(revision_id)
        else:where.append('r.revision_no=(select max(r2.revision_no) from source_document_revision r2 where r2.document_id=d.id)')
        if classification:where.append('s.classification_status=%s');params.append(classification)
        if document:where.append('d.external_doc_id=%s');params.append(document)
        if issue:where.append('exists(select 1 from chunk_issue_tag t where t.tag_set_id=s.proposed_tag_set_id and t.issue_id=%s)');params.append(issue)
        if reason:where.append("exists(select 1 from chunk_review_task t where t.chunk_id=c.id and t.reasons ? %s)");params.append(reason)
        base='''from document_chunk c join chunk_state s on s.chunk_id=c.id join source_document_revision r on r.id=c.revision_id
            join source_document d on d.id=r.document_id
            left join chunk_review_decision cd on cd.id=s.classification_decision_id
            left join chunk_review_decision ad on ad.id=s.content_approval_decision_id where '''+' and '.join(where)
        stats=conn.execute("select count(*) total,count(*) filter(where s.classification_status='classified') classified "+base,params).fetchone()
        items=conn.execute('''select c.id,c.source_chunk_id,c.kind,left(c.text,220) preview,d.title,d.external_doc_id,s.*,
            cd.policy_version classification_policy,ad.policy_version content_policy '''+base+
            ' order by d.external_doc_id,c.seq limit %s offset %s',params+[limit,offset]).fetchall()
        return {'items':items,'total':stats['total'],'classified':stats['classified'],'offset':offset,'limit':limit}

    @app.get('/v1/chunks/{cid}',responses={200:{'description':'Chunk, source, review history and current decision policies.',
        'content':{'application/json':{'schema':{'type':'object','properties':policy_fields}}}}})
    def detail(cid: UUID,user: User,conn: Conn):return service.chunk_detail(conn,cid)

    @app.post('/v1/chunks/{cid}/tags')
    def propose(cid: UUID,body: Proposal,user: User,conn: Conn,idempotency_key: str=Header(default='')):
        return service.propose(conn,user,cid,body.model_dump(mode='json'),idempotency_key)

    @app.post('/v1/chunks/{cid}/decisions')
    def decide(cid: UUID,body: Decision,user: User,conn: Conn,idempotency_key: str=Header(default='')):
        return service.decide(conn,user,cid,body.model_dump(mode='json'),idempotency_key)

    @app.get('/v1/assets/{asset_id}')
    def asset(asset_id: UUID,user: User,conn: Conn):
        row=conn.execute('select * from source_asset where id=%s',(asset_id,)).fetchone()
        if not row:raise ApiError(404,'not_found','Không tìm thấy file nguồn.')
        path=asset_root()/row['storage_key']
        if not path.is_file():raise ApiError(404,'asset_missing','File nguồn chưa được phục hồi.')
        inline=row['mime_type'] in ('image/png','image/jpeg')
        return FileResponse(path,media_type=row['mime_type'] if inline else 'application/octet-stream',
                            filename=row['asset_key'].split('/')[-1],content_disposition_type='inline' if inline else 'attachment',
                            headers={'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

    @app.post('/v1/releases/export')
    def export(body: ReleaseInput,user: User,conn: Conn):
        from app.content.publication import export_release
        return export_release(conn,user,body.version,[str(cid) for cid in body.chunk_ids])

    return app


app=create_app()
