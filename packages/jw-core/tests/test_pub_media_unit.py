"""Unit tests for pub_media client — no network, pure logic on fixed JSON."""

from jw_core.clients.pub_media import Publication, PubMediaClient, PubMediaFile

SAMPLE_RESPONSE = {
    "pubName": "Good News From God!",
    "files": {
        "E": {
            "EPUB": [
                {
                    "title": "Good News From God! (EPUB)",
                    "filesize": 1234567,
                    "mimetype": "application/epub+zip",
                    "file": {
                        "url": "https://cdn.example.com/fg_E.epub",
                        "checksum": "abc123",
                    },
                }
            ],
            "PDF": [
                {
                    "title": "Good News From God! (PDF)",
                    "filesize": 7654321,
                    "mimetype": "application/pdf",
                    "file": {
                        "url": "https://cdn.example.com/fg_E.pdf",
                        "checksum": "def456",
                    },
                }
            ],
        },
        "S": {
            "EPUB": [
                {
                    "title": "Buenas noticias de Dios (EPUB)",
                    "filesize": 1234000,
                    "mimetype": "application/epub+zip",
                    "file": {
                        "url": "https://cdn.example.com/fg_S.epub",
                        "checksum": "ghi789",
                    },
                }
            ],
        },
    },
}


def test_extract_files_groups_by_language_and_format() -> None:
    files = PubMediaClient._extract_files(SAMPLE_RESPONSE)
    assert len(files) == 3
    formats = {f.file_format for f in files}
    assert formats == {"EPUB", "PDF"}
    langs = {f.language for f in files}
    assert langs == {"E", "S"}


def test_publication_files_by_format() -> None:
    pub = Publication(
        pub_code="fg",
        pub_name="Good News From God!",
        files=PubMediaClient._extract_files(SAMPLE_RESPONSE),
    )
    epub_files = pub.files_by_format("EPUB")
    assert len(epub_files) == 2
    assert {f.language for f in epub_files} == {"E", "S"}


def test_publication_files_by_language() -> None:
    pub = Publication(
        pub_code="fg",
        pub_name="x",
        files=PubMediaClient._extract_files(SAMPLE_RESPONSE),
    )
    en_files = pub.files_by_language("E")
    assert len(en_files) == 2
    assert {f.file_format for f in en_files} == {"EPUB", "PDF"}


def test_pubmediafile_filename_derived_from_url() -> None:
    f = PubMediaFile.from_api(
        "E",
        "EPUB",
        {"title": "X", "file": {"url": "https://cdn/foo/bar/fg_E.epub"}},
    )
    assert f.filename == "fg_E.epub"
