"""MagangKu - sistem pencari & pencocok lowongan magang MagangHub Kemnaker.

Alur end-to-end:
    scrape -> normalize -> store -> match (explainable) -> letter -> apply (assisted)

Semua pemrosesan berjalan lokal. Tidak ada kredensial yang dikirim ke pihak ketiga.
"""

from .models import Vacancy
from .profile import Profile
from .matcher import Matcher, MatchResult
from .storage import Store

__version__ = "1.0.0"
__all__ = ["Vacancy", "Profile", "Matcher", "MatchResult", "Store", "__version__"]
