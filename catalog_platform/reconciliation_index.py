"""Disk-backed, read-only catalog comparison. All identifiers stay tenant scoped."""
import hashlib
import json
import sqlite3


def norm(value):
    return str(value or "").strip().casefold()


class CatalogIndex:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE local(id TEXT PRIMARY KEY,sku TEXT,barcode TEXT,kind TEXT,parent TEXT,
                status TEXT,version INTEGER,display TEXT);
            CREATE TABLE remote(id INTEGER PRIMARY KEY,sku TEXT,barcode TEXT,kind TEXT,parent INTEGER,
                status TEXT,display TEXT);
            CREATE TABLE mapping(local TEXT,remote INTEGER,parent INTEGER);
            CREATE TABLE proof(remote INTEGER,parent INTEGER,sku TEXT,stamp TEXT);
            CREATE TABLE lifetime(local TEXT PRIMARY KEY,start TEXT,stop TEXT);
            CREATE INDEX mapped_remote ON mapping(remote);
            CREATE INDEX mapped_local ON mapping(local);
            CREATE INDEX proof_remote ON proof(remote);
            CREATE INDEX local_sku ON local(sku);
            CREATE INDEX local_barcode ON local(barcode);
            CREATE INDEX remote_sku ON remote(sku);
            CREATE INDEX remote_barcode ON remote(barcode);
            CREATE INDEX remote_parent ON remote(parent);
            CREATE TABLE pair(local TEXT,remote INTEGER,PRIMARY KEY(local,remote));
            CREATE INDEX reverse_pair ON pair(remote);
        """)

    def match(self):
        for left in ("sku", "barcode"):
            for right in ("sku", "barcode"):
                self.db.execute(f"""INSERT OR IGNORE INTO pair SELECT l.id,r.id FROM local l
                    JOIN remote r ON l.{left}=r.{right} WHERE l.{left}<>''""")
        self.db.execute("""INSERT OR IGNORE INTO pair SELECT m.local,r.id FROM mapping m
            JOIN remote r ON r.id=m.remote JOIN local l ON l.id=m.local""")

    def classify(self, r):
        db = self.db
        linked = db.execute("SELECT l.* FROM local l JOIN pair p ON l.id=p.local WHERE p.remote=? LIMIT 2",
                            (r["id"],)).fetchall()
        def exists(query, *args):
            return db.execute(query, args).fetchone() is not None
        # Duplicate identities also matter when no local product exists.
        if any(token and exists("SELECT 1 FROM remote WHERE id<>? AND (sku=? OR barcode=?) LIMIT 1",
                                r["id"], token, token) for token in (r["sku"], r["barcode"])):
            return "conflict", None
        if not linked:
            return ("orphan" if r["parent"] and not exists(
                "SELECT 1 FROM pair WHERE remote=?", r["parent"]) else "independent"), None
        l = linked[0]
        if (len(linked)>1 or l["kind"] != r["kind"] or
            not ({l["sku"],l["barcode"]} & {r["sku"],r["barcode"]} - {""}) or
            exists("SELECT 1 FROM pair WHERE local=? AND remote<>?", l["id"], r["id"]) or
            exists("SELECT 1 FROM mapping WHERE local=? AND (remote<>? OR (parent<>0 AND parent<>?))",
                   l["id"], r["id"], r["parent"])):
            return "conflict", l
        if r["parent"]:
            parent = db.execute("""SELECT l.id,l.status FROM pair p JOIN local l ON l.id=p.local
                WHERE p.remote=? LIMIT 2""", (r["parent"],)).fetchall()
            if (len(parent)!=1 or parent[0]["id"] != l["parent"] or
                exists("SELECT 1 FROM pair WHERE local=? AND remote<>?", l["parent"], r["parent"])):
                return "orphan", l
        if l["status"] == "deleted":
            owned = r["sku"] and r["sku"] == l["sku"] and exists("""
                SELECT 1 FROM proof p JOIN lifetime t ON t.local=?
                WHERE p.remote=? AND p.parent=? AND p.sku=? AND p.stamp BETWEEN t.start AND t.stop
                """, l["id"], r["id"], r["parent"], r["sku"])
            if not owned:
                return "unverified", l
            if r["status"] == "draft":
                return "retired", l
            if r["status"] != "publish":
                return "review", l
            # A parent is eligible only after every child has its own verified, completed retirement.
            if r["kind"] == "variable":
                for child in db.execute("SELECT * FROM remote WHERE parent=?", (r["id"],)):
                    if child["kind"]!="variation" or self.classify(child)[0]!="retired":
                        return "family_review", l
            return "remove", l
        if l["status"] == "archived" or r["kind"] not in ("simple","variable","variation"):
            return "review", l
        published = r["status"] == "publish"
        if published and r["parent"]:
            published = exists("SELECT 1 FROM remote WHERE id=? AND status='publish'", r["parent"])
        if (l["status"] == "published") != published:
            return ("publish_local" if published else "unpublish_local"), l
        return "match", l

    def rows(self):
        self.match()
        for r in self.db.execute("SELECT * FROM remote ORDER BY id"):
            category,l = self.classify(r)
            result = self.row(category,l,r)
            if category=="remove" and r["kind"]=="variable":
                children = self.db.execute("SELECT id,sku,barcode,status FROM remote WHERE parent=? ORDER BY id",(r["id"],))
                result["family"] = family_digest(children)
                result["key"] = hashlib.sha256((result["key"]+result["family"]).encode()).hexdigest()
            yield result
        for l in self.db.execute("""SELECT l.* FROM local l WHERE status NOT IN ('deleted','archived')
            AND NOT EXISTS(SELECT 1 FROM pair p WHERE p.local=l.id) ORDER BY id"""):
            duplicate = self.db.execute("""SELECT 1 FROM local WHERE id<>? AND
                ((?<>'' AND (sku=? OR barcode=?)) OR (?<>'' AND (sku=? OR barcode=?))) LIMIT 1""",
                (l["id"],l["sku"],l["sku"],l["sku"],l["barcode"],l["barcode"],l["barcode"])).fetchone()
            yield self.row("conflict" if duplicate else "orphan" if l["parent"] and not
                self.db.execute("SELECT 1 FROM pair WHERE local=?", (l["parent"],)).fetchone() else "missing",l,None)

    @staticmethod
    def row(category,l,r):
        row = dict(category=category,sku=(l or r)["display"],local=l["id"] if l else None,
                   version=l["version"] if l else None,remote=r["id"] if r else None,
                   parent=r["parent"] if r else 0,kind=(r or l)["kind"],
                   remote_status=r["status"] if r else "",remote_sku=r["sku"] if r else "",
                   barcode=r["barcode"] if r else "")
        row["key"] = hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()
        return row


def family_digest(children):
    digest = hashlib.sha256()
    for child in children:
        digest.update(json.dumps(list(child),separators=(",",":")).encode()+b"\n")
    return digest.hexdigest()
