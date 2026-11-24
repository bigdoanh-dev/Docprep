"""Import original-source artifacts into immutable revisions in the authoring database."""
import mimetypes
from uuid import uuid4

from psycopg.types.json import Jsonb

from .auth import audit, require
from .importer import add_taxonomy, store_asset
from .service import canonical, sha


def apply(conn, user, prepared, taxonomy=None):
    require(user, "editor")
    conn.execute("select pg_advisory_xact_lock(7419002)")
    if taxonomy is not None:
        add_taxonomy(conn, taxonomy)
    revisions = []
    for source, path, output, report, chunks in prepared:
        if report["source"] != source.model_dump() or report["chunks"] != len(chunks):
            raise ValueError(f"{source.doc_id}: prepared chunk report does not match import")
        original = path.read_bytes()
        if sha(original) != report["source_sha256"]:
            raise ValueError(f"{source.doc_id}: source changed after chunking")
        artifact = sha(canonical([report, chunks]))
        previous = conn.execute(
            """select r.id, r.revision_no from source_document_revision r
               join source_document d on d.id=r.document_id
               where d.source_namespace='yhdp' and d.external_doc_id=%s and r.artifact_sha256=%s""",
            (source.doc_id, artifact),
        ).fetchone()
        if previous:
            revisions.append({"document": source.doc_id, "revision_id": str(previous["id"]),
                              "revision_no": previous["revision_no"], "reused": True})
            continue
        batch, rev = uuid4(), uuid4()
        conn.execute(
            """insert into content_import_batch(id,source_namespace,archive_sha256,importer_version,
               mapping_version,status,created_by,report) values(%s,'yhdp',%s,%s,'unclassified','completed',%s,%s)""",
            (batch, artifact, report["pipeline"] + ":" + source.doc_id, user["id"], Jsonb(report)),
        )
        document = conn.execute(
            """insert into source_document values(%s,'yhdp',%s,%s,%s,%s,%s,%s)
               on conflict(source_namespace,external_doc_id) do update set title=source_document.title returning id""",
            (uuid4(), source.doc_id, source.title, source.issuer, source.year, source.kind, source.citation),
        ).fetchone()["id"]
        number = conn.execute(
            "select coalesce(max(revision_no),0)+1 n from source_document_revision where document_id=%s", (document,),
        ).fetchone()["n"]
        conn.execute(
            """insert into source_document_revision(id,document_id,revision_no,batch_id,artifact_sha256,
               parser_version,chunker_version,source_availability) values(%s,%s,%s,%s,%s,%s,%s,'original_docx')""",
            (rev, document, number, batch, artifact, report["pipeline"] + ":" + source.format, report["pipeline"]),
        )
        files = [("original.docx", "original", path)]
        files += [(f.relative_to(output / "assets").as_posix() if f.is_relative_to(output / "assets") else f.name,
                   "derived", f) for f in sorted(output.rglob("*")) if f.is_file()]
        for name, role, file in files:
            data = original if role == "original" else file.read_bytes()
            key = store_asset(data)
            conn.execute("insert into source_asset values(%s,%s,%s,%s,%s,%s,%s,%s)",
                         (uuid4(), rev, name, role, mimetypes.guess_type(name)[0] or "application/octet-stream",
                          len(data), key, key))
        for seq, row in enumerate(chunks):
            cid, loc = uuid4(), row["location"]
            search = f"{loc['augmentation']['contextual_header']}\n\n{row['text']}"
            conn.execute(
                "insert into document_chunk values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (cid, rev, row["chunk_id"], seq, row["kind"], row["text"], search, Jsonb(loc), row["tokens"],
                 sha(canonical([row["text"], loc, row["kind"]])), row["content_hash"],
                 Jsonb(row["needs_review"]), Jsonb(row["refs"])),
            )
            conn.execute("insert into chunk_state(chunk_id) values(%s)", (cid,))
            for purpose, reasons in (("classification", ["new_source_revision"]),
                                     ("content", ["new_source_revision", *row["needs_review"]])):
                conn.execute("insert into chunk_review_task values(%s,%s,%s,'open',%s)",
                             (uuid4(), cid, purpose, Jsonb(reasons)))
        audit(conn, user["id"], "rechunk_import", batch, {"document": source.doc_id, "revision": number})
        revisions.append({"document": source.doc_id, "revision_id": str(rev), "revision_no": number, "reused": False})
    return revisions
