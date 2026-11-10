import os
import tempfile
import unittest

from mfpipe import sync


class SyncConfig(unittest.TestCase):
    def test_env_file_and_override(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".env")
            open(p, "w").write('# c\nDATABASE_URL="postgresql://u:p@h:5432/db"\nMF_SQL_DIR=/x\n')
            env = sync.load_env(p, environ={"MF_SQL_DIR": "/y"})
            self.assertEqual(env["DATABASE_URL"], "postgresql://u:p@h:5432/db")
            self.assertEqual(env["MF_SQL_DIR"], "/y")  # real env wins

    def test_mask(self):
        self.assertEqual(sync.mask("failed postgresql://user:s3cret@10.0.0.5:5432/db"),
                         "failed postgresql://user:***@10.0.0.5:5432/db")

    def test_database_url(self):
        self.assertEqual(sync.database_url({"DATABASE_URL": "postgresql://a"}), "postgresql://a")
        self.assertEqual(sync.database_url({"PGHOST": "h"}), "postgresql://")
        self.assertIsNone(sync.database_url({}))


if __name__ == "__main__":
    unittest.main()
