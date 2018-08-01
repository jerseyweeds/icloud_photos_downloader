from unittest import TestCase
from vcr import VCR
import os
import shutil
import logging
import click
import pytest
import mock
from mock import call, ANY
from click.testing import CliRunner
import piexif
from piexif._exceptions import InvalidImageDataError
from pyicloud_ipd.services.photos import PhotoAsset
from pyicloud_ipd.base import PyiCloudService
from pyicloud_ipd.exceptions import PyiCloudAPIResponseError
from requests.exceptions import ConnectionError
from icloudpd.base import main
import icloudpd.constants

vcr = VCR(decode_compressed_response=True)


class DownloadPhotoTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def test_download_photos(self):
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        os.makedirs("tests/fixtures/Photos/2018/07/30/")
        open("tests/fixtures/Photos/2018/07/30/IMG_7408-original.JPG", "a").close()
        open("tests/fixtures/Photos/2018/07/30/IMG_7407-original.JPG", "a").close()

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "5",
                    "--skip-videos",
                    "--set-exif-datetime",
                    "--no-progress-bar",
                    "tests/fixtures/Photos",
                ],
            )
            print(result.exception)
            self.assertIn("DEBUG    Looking up all photos...", self._caplog.text)
            self.assertIn(
                "INFO     Downloading 5 original photos to tests/fixtures/Photos/ ...",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Downloading tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     tests/fixtures/Photos/2018/07/30/IMG_7408-original.JPG already exists.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     tests/fixtures/Photos/2018/07/30/IMG_7407-original.JPG already exists.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Skipping IMG_7405.MOV, only downloading photos.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     Skipping IMG_7404.MOV, only downloading photos.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0

    def test_download_photos_and_set_exif(self):
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        os.makedirs("tests/fixtures/Photos/2018/07/30/")
        open("tests/fixtures/Photos/2018/07/30/IMG_7408-original.JPG", "a").close()
        open("tests/fixtures/Photos/2018/07/30/IMG_7407-original.JPG", "a").close()

        # Download the first photo, but mock the video download
        orig_download = PhotoAsset.download

        def mocked_download(self, size):
            if not hasattr(PhotoAsset, "already_downloaded"):
                response = orig_download(self, size)
                setattr(PhotoAsset, "already_downloaded", True)
                return response
            return mock.MagicMock()

        with mock.patch.object(PhotoAsset, "download", new=mocked_download):
            with mock.patch(
                "icloudpd.exif_datetime.get_photo_exif"
            ) as get_exif_patched:
                get_exif_patched.return_value = False
                with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
                    # Pass fixed client ID via environment variable
                    os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
                    runner = CliRunner()
                    result = runner.invoke(
                        main,
                        [
                            "--username",
                            "jdoe@gmail.com",
                            "--password",
                            "password1",
                            "--recent",
                            "4",
                            "--set-exif-datetime",
                            # '--skip-videos',
                            "--no-progress-bar",
                            "tests/fixtures/Photos",
                        ],
                    )
                    print(result.exception)

                    self.assertIn(
                        "DEBUG    Looking up all photos and videos...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     Downloading 4 original photos and videos to tests/fixtures/Photos/ ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     Downloading tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG",
                        self._caplog.text,
                    )
                    # YYYY:MM:DD is the correct format.
                    self.assertIn(
                        "DEBUG    Setting EXIF timestamp for tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG: 2018:07:31",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     All photos have been downloaded!", self._caplog.text
                    )
                    assert result.exit_code == 0

    def test_download_photos_and_exif_exceptions(self):
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        with mock.patch.object(piexif, "load") as piexif_patched:
            piexif_patched.side_effect = InvalidImageDataError

            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
                # Pass fixed client ID via environment variable
                os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
                runner = CliRunner()
                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--recent",
                        "1",
                        "--skip-videos",
                        "--set-exif-datetime",
                        "--no-progress-bar",
                        "tests/fixtures/Photos",
                    ],
                )
                self.assertIn("DEBUG    Looking up all photos...", self._caplog.text)
                self.assertIn(
                    "INFO     Downloading the first original photo to tests/fixtures/Photos/ ...",
                    self._caplog.text,
                )
                self.assertIn(
                    "INFO     Downloading tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG",
                    self._caplog.text,
                )
                self.assertIn(
                    "DEBUG    Error fetching EXIF data for tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG",
                    self._caplog.text,
                )
                self.assertIn(
                    "DEBUG    Error setting EXIF data for tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG",
                    self._caplog.text,
                )
                self.assertIn(
                    "INFO     All photos have been downloaded!", self._caplog.text
                )
                assert result.exit_code == 0

    def test_skip_existing_downloads(self):
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos/2018/07/31/")
        shutil.copyfile(
            "tests/fixtures/IMG_7409-original.JPG",
            "tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG",
        )

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--username",
                    "jdoe@gmail.com",
                    "--password",
                    "password1",
                    "--recent",
                    "1",
                    # '--skip-videos',
                    "--no-progress-bar",
                    "tests/fixtures/Photos",
                ],
            )
            self.assertIn(
                "DEBUG    Looking up all photos and videos...", self._caplog.text
            )
            self.assertIn(
                "INFO     Downloading the first original photo or video to tests/fixtures/Photos/ ...",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG already exists.",
                self._caplog.text,
            )
            self.assertIn(
                "INFO     All photos have been downloaded!", self._caplog.text
            )
            assert result.exit_code == 0

    def test_until_found(self):
        base_dir = "tests/fixtures/Photos"
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos/2018/07/30/")
        os.makedirs("tests/fixtures/Photos/2018/07/31/")

        files_to_download = []
        files_to_skip = []

        files_to_download.append("2018/07/31/IMG_7409-original.JPG")
        files_to_skip.append("2018/07/30/IMG_7408-original.JPG")
        files_to_download.append("2018/07/30/IMG_7407-original.JPG")
        files_to_skip.append("2018/07/30/IMG_7405-original.MOV")
        files_to_skip.append("2018/07/30/IMG_7404-original.MOV")
        files_to_download.append("2018/07/30/IMG_7403-original.MOV")
        files_to_download.append("2018/07/30/IMG_7402-original.MOV")
        files_to_skip.append("2018/07/30/IMG_7401-original.MOV")
        files_to_skip.append("2018/07/30/IMG_7400-original.JPG")
        files_to_skip.append("2018/07/30/IMG_7399-original.JPG")

        for f in files_to_skip:
            open("%s/%s" % (base_dir, f), "a").close()

        with mock.patch("icloudpd.download.download_photo") as dp_patched:
            dp_patched.return_value = True
            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
                # Pass fixed client ID via environment variable
                os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
                runner = CliRunner()
                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--until-found",
                        "3",
                        "--recent",
                        "20",
                        "--no-progress-bar",
                        base_dir,
                    ],
                )
                print(result.exception)
                expected_calls = list(
                    map(
                        lambda f: call(ANY, ANY, "%s/%s" % (base_dir, f), "original"),
                        files_to_download,
                    )
                )
                dp_patched.assert_has_calls(expected_calls)

                self.assertIn(
                    "DEBUG    Looking up all photos and videos...", self._caplog.text
                )
                self.assertIn(
                    "INFO     Downloading ??? original photos and videos to tests/fixtures/Photos/ ...",
                    self._caplog.text,
                )

                for f in files_to_skip:
                    expected_message = "INFO     %s/%s already exists." % (base_dir, f)
                    self.assertIn(expected_message, self._caplog.text)

                self.assertIn(
                    "INFO     Found 3 consecutive previously downloaded photos. Exiting",
                    self._caplog.text,
                )
                assert result.exit_code == 0

    def test_handle_io_error(self):
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"

            with mock.patch("icloudpd.download.open", create=True) as m:
                # Raise IOError when we try to write to the destination file
                m.side_effect = IOError

                runner = CliRunner()
                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--recent",
                        "1",
                        "--skip-videos",
                        "--no-progress-bar",
                        "tests/fixtures/Photos",
                    ],
                )
                self.assertIn("DEBUG    Looking up all photos...", self._caplog.text)
                self.assertIn(
                    "INFO     Downloading the first original photo to tests/fixtures/Photos/ ...",
                    self._caplog.text,
                )
                self.assertIn(
                    "ERROR    IOError while writing file to "
                    "tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG! "
                    "You might have run out of disk space, or the file might "
                    "be too large for your OS. Skipping this file...",
                    self._caplog.text,
                )
                assert result.exit_code == 0

    def test_handle_session_error(self):
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"

            def mock_raise_response_error(arg):
                raise PyiCloudAPIResponseError("Invalid global session", 100)

            with mock.patch("icloudpd.constants.WAIT_SECONDS", 0):
                with mock.patch.object(PhotoAsset, "download") as pa_download:
                    pa_download.side_effect = mock_raise_response_error

                    # Let the initial authenticate() call succeed,
                    # but do nothing on the second try.
                    orig_authenticate = PyiCloudService.authenticate

                    def mocked_authenticate(self):
                        if not hasattr(self, "already_authenticated"):
                            orig_authenticate(self)
                            setattr(self, "already_authenticated", True)

                    with mock.patch.object(
                        PyiCloudService, "authenticate", new=mocked_authenticate
                    ):
                        runner = CliRunner()
                        result = runner.invoke(
                            main,
                            [
                                "--username",
                                "jdoe@gmail.com",
                                "--password",
                                "password1",
                                "--recent",
                                "1",
                                "--skip-videos",
                                "--no-progress-bar",
                                "tests/fixtures/Photos",
                            ],
                        )
                        # Error msg should be repeated 5 times
                        assert (
                            self._caplog.text.count(
                                "Session error, re-authenticating..."
                            )
                            == 5
                        )

                        self.assertIn(
                            "INFO     Could not download IMG_7409.JPG! Please try again later.",
                            self._caplog.text,
                        )
                        assert result.exit_code == 0

    def test_handle_connection_error(self):
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
            # Pass fixed client ID via environment variable
            os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"

            def mock_raise_response_error(arg):
                raise ConnectionError("Connection Error")

            with mock.patch.object(PhotoAsset, "download") as pa_download:
                pa_download.side_effect = mock_raise_response_error

                # Let the initial authenticate() call succeed,
                # but do nothing on the second try.
                orig_authenticate = PyiCloudService.authenticate

                def mocked_authenticate(self):
                    if not hasattr(self, "already_authenticated"):
                        orig_authenticate(self)
                        setattr(self, "already_authenticated", True)

                with mock.patch("icloudpd.constants.WAIT_SECONDS", 0):
                    with mock.patch.object(
                        PyiCloudService, "authenticate", new=mocked_authenticate
                    ):
                        runner = CliRunner()
                        result = runner.invoke(
                            main,
                            [
                                "--username",
                                "jdoe@gmail.com",
                                "--password",
                                "password1",
                                "--recent",
                                "1",
                                "--skip-videos",
                                "--no-progress-bar",
                                "tests/fixtures/Photos",
                            ],
                        )
                        # Error msg should be repeated 5 times
                        assert (
                            self._caplog.text.count(
                                "Error downloading IMG_7409.JPG, retrying after 0 seconds..."
                            )
                            == 5
                        )

                        self.assertIn(
                            "INFO     Could not download IMG_7409.JPG! Please try again later.",
                            self._caplog.text,
                        )
                        assert result.exit_code == 0

    def test_missing_size(self):
        base_dir = "tests/fixtures/Photos"
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        with mock.patch.object(PhotoAsset, "download") as pa_download:
            pa_download.return_value = False

            with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
                # Pass fixed client ID via environment variable
                os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
                runner = CliRunner()
                result = runner.invoke(
                    main,
                    [
                        "--username",
                        "jdoe@gmail.com",
                        "--password",
                        "password1",
                        "--recent",
                        "3",
                        "--no-progress-bar",
                        base_dir,
                    ],
                )
                print(result.exception)

                self.assertIn(
                    "DEBUG    Looking up all photos and videos...", self._caplog.text
                )
                self.assertIn(
                    "INFO     Downloading 3 original photos and videos to tests/fixtures/Photos/ ...",
                    self._caplog.text,
                )

                # These error messages should not be repeated more than once
                assert (
                    self._caplog.text.count(
                        "ERROR    Could not find URL to download IMG_7409.JPG for size original!"
                    )
                    == 1
                )
                assert (
                    self._caplog.text.count(
                        "ERROR    Could not find URL to download IMG_7408.JPG for size original!"
                    )
                    == 1
                )
                assert (
                    self._caplog.text.count(
                        "ERROR    Could not find URL to download IMG_7407.JPG for size original!"
                    )
                    == 1
                )

                self.assertIn(
                    "INFO     All photos have been downloaded!", self._caplog.text
                )
                assert result.exit_code == 0

    def test_size_fallback_to_original(self):
        base_dir = "tests/fixtures/Photos"
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        with mock.patch("icloudpd.download.download_photo") as dp_patched:
            dp_patched.return_value = True

            with mock.patch.object(PhotoAsset, "versions") as pa:
                pa.return_value = ["original", "medium"]

                with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
                    # Pass fixed client ID via environment variable
                    os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
                    runner = CliRunner()
                    result = runner.invoke(
                        main,
                        [
                            "--username",
                            "jdoe@gmail.com",
                            "--password",
                            "password1",
                            "--recent",
                            "1",
                            "--size",
                            "thumb",
                            "--no-progress-bar",
                            base_dir,
                        ],
                    )
                    print(result.exception)

                    self.assertIn(
                        "DEBUG    Looking up all photos and videos...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     Downloading the first thumb photo or video to tests/fixtures/Photos/ ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     Downloading tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     All photos have been downloaded!", self._caplog.text
                    )
                    dp_patched.assert_called_once_with(
                        ANY,
                        ANY,
                        "tests/fixtures/Photos/2018/07/31/IMG_7409-original.JPG",
                        "original",
                    )

                    assert result.exit_code == 0

    def test_force_size(self):
        base_dir = "tests/fixtures/Photos"
        if os.path.exists("tests/fixtures/Photos"):
            shutil.rmtree("tests/fixtures/Photos")
        os.makedirs("tests/fixtures/Photos")

        with mock.patch("icloudpd.download.download_photo") as dp_patched:
            dp_patched.return_value = True

            with mock.patch.object(PhotoAsset, "versions") as pa:
                pa.return_value = ["original", "medium"]

                with vcr.use_cassette("tests/vcr_cassettes/listing_photos.yml"):
                    # Pass fixed client ID via environment variable
                    os.environ["CLIENT_ID"] = "DE309E26-942E-11E8-92F5-14109FE0B321"
                    runner = CliRunner()
                    result = runner.invoke(
                        main,
                        [
                            "--username",
                            "jdoe@gmail.com",
                            "--password",
                            "password1",
                            "--recent",
                            "1",
                            "--size",
                            "thumb",
                            "--force-size",
                            "--no-progress-bar",
                            base_dir,
                        ],
                    )
                    print(result.exception)

                    self.assertIn(
                        "DEBUG    Looking up all photos and videos...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     Downloading the first thumb photo or video to tests/fixtures/Photos/ ...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "ERROR    thumb size does not exist for IMG_7409.JPG. Skipping...",
                        self._caplog.text,
                    )
                    self.assertIn(
                        "INFO     All photos have been downloaded!", self._caplog.text
                    )
                    dp_patched.assert_not_called

                    assert result.exit_code == 0
