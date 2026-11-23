"""Offline-only release asset preview invariants."""
import importlib.util
import json
from pathlib import Path
import contextlib
import io
import unittest
import urllib.request
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gitlab_assets',ROOT/'tools/release/gitlab_assets.py')
assets=importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)
stage_spec=importlib.util.spec_from_file_location('stage',ROOT/'tools/stage/stage.py')
stage=importlib.util.module_from_spec(stage_spec)
stage_spec.loader.exec_module(stage)


class ReleaseAssetTests(unittest.TestCase):
    def make_fixture(self,root):
        config_path=root/'config.json'
        config_path.write_text(json.dumps({
            'api_url':'https://gitlab.example.test/api/v4',
            'project':'group/project',
            'expected_project':'group/project'
        }))
        installer=root/'InteractiveMissions.mltbx'
        installer.write_bytes(b'fixture installer')
        checksum=assets.sha256(installer)
        installer.with_name('InteractiveMissions.mltbx.sha256').write_text(checksum+'  InteractiveMissions.mltbx\n')
        return config_path,installer,checksum

    def test_release_preview_is_offline_and_marks_no_write(self):
        with stage.temporary_directory() as temporary:
            config_path,installer,checksum=self.make_fixture(Path(temporary))
            config=assets.load_config(config_path)
            with patch.object(urllib.request,'urlopen') as urlopen:
                result=assets.preview_release(config,installer,'v1.2.3','a'*40)
            urlopen.assert_not_called()
            self.assertEqual(result['status'],'preview_only')
            self.assertFalse(result['remote_write_performed'])
            self.assertEqual(result['assets'][0]['sha256'],checksum)
            self.assertIn('/packages/generic/interactive-missions/v1.2.3/',result['assets'][0]['registry_path'])
            self.assertIn('no GitLab Release was created',result['message'])

    def test_upload_preview_is_offline_and_creates_no_receipt(self):
        with stage.temporary_directory() as temporary:
            root=Path(temporary)
            config_path,_,_=self.make_fixture(root)
            config=assets.load_config(config_path)
            evidence=root/'evidence.tar.gz'
            evidence.write_bytes(b'local evidence')
            with patch.object(urllib.request,'urlopen') as urlopen:
                result=assets.preview_upload(config,evidence,'evaluation-evidence','snapshot-1')
            urlopen.assert_not_called()
            self.assertFalse(result['remote_write_performed'])
            self.assertFalse(evidence.with_name(evidence.name+'.registry-receipt.json').exists())
            self.assertIn('No GitLab package was uploaded',result['message'])

    def test_execute_flag_is_not_supported(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                assets.build_parser().parse_args(['preview-release','--config','config.json','--execute'])

    def test_ci_has_no_gitlab_request_or_publication_command(self):
        config=(ROOT/'.gitlab-ci.yml').read_text(encoding='utf-8').lower()
        for forbidden in ('curl', '--execute', 'private-token', 'gitlab_token', 'packages/generic', '/releases'):
            self.assertNotIn(forbidden,config)
        self.assertIn('release_publication_disabled',config)
        self.assertIn('gitlab_writes_performed',config)
        self.assertIn('when: manual',config)
        self.assertEqual(config.count('when: never'),1)


if __name__=='__main__': unittest.main()
