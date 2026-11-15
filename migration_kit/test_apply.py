import tempfile, pathlib, subprocess, sys
from unittest.mock import patch as mock_patch
from apply import deploy
with tempfile.TemporaryDirectory() as t:
    r=pathlib.Path(t); src=r/'source';src.mkdir();(src/'a.txt').write_text('new')
    dest=r/'atomic';assert deploy(src,dest,'atomic')['a.txt'];assert (dest/'a.txt').read_text()=='new'
    other=r/'overlay';other.mkdir();(other/'a.txt').write_text('old');deploy(src,other,'overlay');assert (other/'a.txt').read_text()=='new';assert (r/'overlay.backup'/'a.txt').read_text()=='old'
    patch=r/'change.patch';patch.write_text('--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-old\n+new\n')
    third=r/'patch';third.mkdir();(third/'a.txt').write_text('old\n');deploy(src,third,'patch',patch);assert (third/'a.txt').read_text()=='new\n'
    assert not (third/'.git').exists()
    no_git=r/'no-git';no_git.mkdir();(no_git/'a.txt').write_text('old\n')
    with mock_patch('apply.shutil.which',return_value=None):
        try: deploy(src,no_git,'patch',patch)
        except RuntimeError as exc: assert 'use atomic' in str(exc) and 'No Git metadata is created' in str(exc)
        else: raise AssertionError('patch mode must explain how to proceed when Git is missing')
    assert (no_git/'a.txt').read_text()=='old\n' and not (r/'no-git.backup').exists()
print('DEPLOYMENT_METHODS 3/3 PASS')
