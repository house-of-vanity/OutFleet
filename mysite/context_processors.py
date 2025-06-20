from django.conf import settings
import subprocess
from pathlib import Path

def version_info(request):
    """Add version information to template context"""
    
    git_commit = getattr(settings, 'GIT_COMMIT', None)
    git_commit_short = getattr(settings, 'GIT_COMMIT_SHORT', None)
    build_date = getattr(settings, 'BUILD_DATE', None)
    
    if not git_commit or git_commit == 'development':
        try:
            base_dir = getattr(settings, 'BASE_DIR', Path(__file__).resolve().parent.parent)
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, cwd=base_dir, timeout=5)
            if result.returncode == 0:
                git_commit = result.stdout.strip()
                git_commit_short = git_commit[:7]
                
                date_result = subprocess.run(['git', 'log', '-1', '--format=%ci'], 
                                           capture_output=True, text=True, cwd=base_dir, timeout=5)
                if date_result.returncode == 0:
                    build_date = date_result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            pass
    
    if not git_commit:
        git_commit = 'development'
    if not git_commit_short:
        git_commit_short = 'dev'
    if not build_date:
        build_date = 'unknown'
    
    return {
        'VERSION_INFO': {
            'git_commit': git_commit,
            'git_commit_short': git_commit_short,
            'build_date': build_date,
            'is_development': git_commit_short == 'dev'
        }
    }
