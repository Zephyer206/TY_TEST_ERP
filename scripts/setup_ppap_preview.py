"""Stage the pinned, hash-verified Windows Excel preview runtime locally.

Usage: .venv\Scripts\python.exe scripts\setup_ppap_preview.py [--check]
No system installation is performed. Source documents never leave this server.
"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import urllib.request

VERSION = '26.2.6'
SHA256 = 'f9877032fd908beb9c0ddf06df4af5c2e85f419c42e14876c4cce5aae5fb2660'
PROJECT = Path(__file__).resolve().parents[1]


def digest(path):
    if not path.is_file():
        return ''
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check an existing converter without downloading')
    args = parser.parse_args()
    target = PROJECT / 'runtime/tools/libreoffice'
    executable = Path(os.environ['PPAP_SOFFICE']) if os.environ.get('PPAP_SOFFICE') else target / 'program/soffice.com'
    if not args.check and not executable.is_file():
        if os.name != 'nt':
            raise SystemExit('Install LibreOffice and configure PPAP_SOFFICE on this platform.')
        installer = PROJECT / f'runtime/tools/LibreOffice_{VERSION}_Win_x86-64.msi'
        installer.parent.mkdir(parents=True, exist_ok=True)
        if digest(installer) != SHA256:
            # Mirror and digest verified from the official mirrorlist:
            # https://download.documentfoundation.org/libreoffice/stable/26.2.6/win/x86_64/LibreOffice_26.2.6_Win_x86-64.msi.mirrorlist
            url = f'https://mirrors.nju.edu.cn/tdf/libreoffice/stable/{VERSION}/win/x86_64/LibreOffice_{VERSION}_Win_x86-64.msi'
            request = urllib.request.Request(url, headers={'User-Agent': 'ZephyrERP-PPAP-preview-setup'})
            with urllib.request.urlopen(request, timeout=120) as response, installer.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        if digest(installer) != SHA256:
            raise SystemExit('Installer checksum mismatch; extraction was not attempted.')
        completed = subprocess.run(['msiexec.exe', '/a', str(installer), '/qn', 'TARGETDIR=' + str(target)], timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode != 0:
            raise SystemExit(f'Local runtime extraction failed: {completed.returncode}')
    if not executable.is_file():
        raise SystemExit('Converter not found. Configure PPAP_SOFFICE or run setup without --check.')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    result = subprocess.run([str(executable), '--headless', '--version'], capture_output=True, timeout=30, creationflags=flags)
    if result.returncode:
        raise SystemExit('Converter could not start.')
    print(result.stdout.decode(errors='replace').strip())
    print('PPAP preview runtime ready')


if __name__ == '__main__':
    main()
