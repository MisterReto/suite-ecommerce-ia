"""Drive boundary, preserving existing folders and legacy SDK compatibility."""

import io
import re
from pathlib import Path
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload


class DriveService:
    def __init__(self, client, root_id=None):
        self.client, self.root_id = client, root_id

    def files(self):
        # Compatibility boundary: old capture/media modules keep their proven calls.
        return self.client.files()

    @classmethod
    def for_session(cls, runtime, value):
        client = runtime._get_drive_service(value)
        root, _, _, _ = runtime._preparar_estructura(client, value)
        service = client if isinstance(client, cls) else cls(client)
        service.root_id = root
        return service

    def list(
        self, folder=None, query="", fields="id,name,mimeType,parents", limit=5000
    ):
        parent = folder or self.root_id
        if not parent or not re.fullmatch(r"[A-Za-z0-9_-]+", parent):
            raise ValueError("Carpeta Drive inválida.")
        rows, page = [], None
        while True:
            result = (
                self.files()
                .list(
                    q=f"'{parent}' in parents and trashed=false"
                    + (" and " + query if query else ""),
                    fields=f"nextPageToken,files({fields})",
                    pageSize=100,
                    pageToken=page,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            rows.extend(result.get("files", []))
            if len(rows) > limit:
                raise ValueError("La carpeta excede el límite de esta operación.")
            page = result.get("nextPageToken")
            if not page:
                return rows

    def folder(self, name, parent=None):
        parent = parent or self.root_id
        if not parent:
            raise ValueError("Selecciona la carpeta de trabajo primero.")
        safe = name.replace("\\", "\\\\").replace("'", "\\'")
        rows = self.list(
            parent, f"name='{safe}' and mimeType='application/vnd.google-apps.folder'"
        )
        if len(rows) > 1:
            raise ValueError(
                "Hay carpetas duplicadas. Selecciona la carpeta correcta por ID."
            )
        if rows:
            return rows[0]["id"]
        return (
            self.files()
            .create(
                body={
                    "name": name,
                    "parents": [parent],
                    "mimeType": "application/vnd.google-apps.folder",
                },
                fields="id",
                supportsAllDrives=True,
            )
            .execute()["id"]
        )

    def working_folder(self, *parts):
        parent = self.folder("Rincon_de_Asia_App")
        for part in parts:
            parent = self.folder(part, parent)
        return parent

    def owns(self, file_id):
        pending, seen = [file_id], set()
        for _ in range(10):
            if self.root_id in pending:
                return True
            next_ids = []
            for item in pending:
                if item in seen:
                    continue
                seen.add(item)
                info = (
                    self.files()
                    .get(
                        fileId=item, fields="id,parents,trashed", supportsAllDrives=True
                    )
                    .execute()
                )
                if not info.get("trashed"):
                    next_ids.extend(info.get("parents", []))
            pending = next_ids
            if not pending:
                break
        return False

    def download(self, file_id):
        if not self.owns(file_id):
            raise ValueError("El archivo no pertenece a la carpeta de trabajo.")
        with io.BytesIO() as stream:
            self._download(file_id, stream)
            return stream.getvalue()

    def _download(self, file_id, stream):
        fetch = MediaIoBaseDownload(stream,
            self.files().get_media(fileId=file_id, supportsAllDrives=True),
            chunksize=512 * 1024)
        done = False
        while not done:
            _, done = fetch.next_chunk()
            if stream.tell() > 12_000_000:
                raise ValueError("La imagen supera 12 MB.")

    def download_to(self, file_id, destination):
        """Stream to this process's /tmp; never materialize a batch in RAM."""
        path = Path(destination).resolve()
        if path.parent != Path("/tmp") or not self.owns(file_id):
            raise ValueError("Archivo o destino temporal no autorizado.")
        try:
            with path.open("wb") as stream:
                self._download(file_id, stream)
            return str(path)
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def metadata(self, file_id):
        if not self.owns(file_id):
            raise ValueError("Archivo no autorizado.")
        return self.files().get(fileId=file_id, supportsAllDrives=True,
            fields="id,name,mimeType,size,parents,md5Checksum,appProperties,webViewLink").execute()

    def find(self, name, folder=None):
        safe = name.replace("\\", "\\\\").replace("'", "\\'")
        return self.list(folder, f"name='{safe}'")

    @staticmethod
    def url(file_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
            raise ValueError("ID Drive inválido.")
        return "https://drive.google.com/file/d/" + file_id + "/view"

    def save_approved(self, path, filename, folder, asset_id):
        """Explicit approval/save only. Back up an existing canonical file first."""
        if not self.owns(folder):
            raise ValueError("Carpeta de destino no autorizada.")
        matches = self.find(filename, folder)
        if len(matches) > 1:
            raise ValueError("Hay nombres duplicados; selecciona el archivo por ID antes de guardar.")
        if not matches:
            return self.upload(path, filename, folder, {"asset_id": asset_id})
        old = matches[0]
        metadata = self.metadata(old["id"])
        if metadata.get("appProperties", {}).get("asset_id") == asset_id:
            return old
        # Deterministic backup names also make a retried explicit save safe.
        backup_folder = self.working_folder("backups", "images")
        backup_name = old["id"] + "_before_" + asset_id + ".jpg"
        if not self.find(backup_name, backup_folder):
            self.files().copy(fileId=old["id"], supportsAllDrives=True,
                body={"name": backup_name, "parents": [backup_folder]}, fields="id").execute()
        return self.files().update(fileId=old["id"], supportsAllDrives=True,
            body={"appProperties": {**metadata.get("appProperties", {}), "asset_id": asset_id}},
            media_body=MediaFileUpload(str(path), mimetype="image/jpeg", resumable=False),
            fields="id,name,size").execute()

    def upload(self, path, filename, folder, properties=None):
        if not self.owns(folder):
            raise ValueError("La carpeta de destino no está autorizada.")
        media = MediaFileUpload(str(path), mimetype="image/jpeg", resumable=False)
        return (
            self.files()
            .create(
                body={
                    "name": filename,
                    "parents": [folder],
                    "appProperties": properties or {},
                },
                media_body=media,
                fields="id,name,size",
                supportsAllDrives=True,
            )
            .execute()
        )

    def backup(self, file_id, label):
        if not self.owns(file_id):
            raise ValueError("La fuente de respaldo no está autorizada.")
        parent = self.working_folder("backups")
        return (
            self.files()
            .copy(
                fileId=file_id,
                body={"name": label, "parents": [parent]},
                fields="id,name",
                supportsAllDrives=True,
            )
            .execute()
        )

    def upload_bytes(self, data, filename, folder, mime_type):
        if not self.owns(folder):
            raise ValueError("La carpeta de destino no está autorizada.")
        return (
            self.files()
            .create(
                body={"name": filename, "parents": [folder]},
                media_body=MediaIoBaseUpload(
                    io.BytesIO(data), mimetype=mime_type, resumable=False
                ),
                fields="id,name",
                supportsAllDrives=True,
            )
            .execute()
        )

    def export(
        self,
        file_id,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ):
        if not self.owns(file_id):
            raise ValueError("La hoja no pertenece a esta carpeta.")
        return self.files().export_media(fileId=file_id, mimeType=mime).execute()
