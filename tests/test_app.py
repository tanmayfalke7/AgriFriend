import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1] / 'backend'))
from app import services
def test_chunking_never_empty(): assert services.chunk('alpha ' * 200)
def test_language_detection(): assert services.language_for('What is cotton?') == 'en'
def test_fallback_is_safe(): assert 'reliable' in services.fallback('en').lower()
