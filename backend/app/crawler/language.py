from collections import Counter
from urllib.parse import urlparse

ISO_639_1 = frozenset(
    {
        "aa", "ab", "ae", "af", "ak", "am", "an", "ar", "as", "av", "ay", "az",
        "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo", "br", "bs",
        "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv", "cy",
        "da", "de", "dv", "dz",
        "ee", "el", "en", "eo", "es", "et", "eu",
        "fa", "ff", "fi", "fj", "fo", "fr", "fy",
        "ga", "gd", "gl", "gn", "gu", "gv",
        "ha", "he", "hi", "ho", "hr", "ht", "hu", "hy", "hz",
        "ia", "id", "ie", "ig", "ii", "ik", "io", "is", "it", "iu",
        "ja", "jv",
        "ka", "kg", "ki", "kj", "kk", "kl", "km", "kn", "ko", "kr", "ks", "ku", "kv", "kw", "ky",
        "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv",
        "mg", "mh", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my",
        "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr", "nv", "ny",
        "oc", "oj", "om", "or", "os",
        "pa", "pi", "pl", "ps", "pt",
        "qu",
        "rm", "rn", "ro", "ru", "rw",
        "sa", "sc", "sd", "se", "sg", "si", "sk", "sl", "sm", "sn", "so", "sq", "sr", "ss", "st", "su", "sv", "sw",
        "ta", "te", "tg", "th", "ti", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty",
        "ug", "uk", "ur", "uz",
        "ve", "vi", "vo",
        "wa", "wo",
        "xh",
        "yi", "yo",
        "za", "zh", "zu",
    }
)


def normalize_locale(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip().lower().replace("_", "-")
    if raw in {"x-default", "default"}:
        return "x-default"
    primary = raw.split("-", 1)[0]
    if primary in ISO_639_1:
        return primary
    return None


def first_path_segment(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return ""
    return path.split("/", 1)[0].lower()


def lang_from_path(url: str, prefix_langs: set[str] | None = None) -> str | None:
    segment = first_path_segment(url)
    candidate = normalize_locale(segment)
    if candidate is None:
        return None
    if prefix_langs is not None and candidate not in prefix_langs:
        return None
    return candidate


def discover_prefix_langs(urls: list[str], min_pages: int = 2) -> set[str]:
    counts: Counter[str] = Counter()
    for url in urls:
        lang = lang_from_path(url)
        if lang:
            counts[lang] += 1
    return {lang for lang, count in counts.items() if count >= min_pages}


def infer_default_lang(
    hreflang_pairs: list[tuple[str, str, str]],
    seed_url: str,
    html_langs: list[str] | None = None,
) -> str:
    for _source, lang, target in hreflang_pairs:
        if lang == "x-default":
            path_lang = lang_from_path(target)
            if path_lang:
                return path_lang
            for source, other, dest in hreflang_pairs:
                if dest == target and other not in {None, "x-default"}:
                    return other
                _ = source
    seed_lang = lang_from_path(seed_url)
    if seed_lang:
        return seed_lang
    if html_langs:
        counts = Counter(lang for lang in html_langs if lang)
        if counts:
            return counts.most_common(1)[0][0]
    return "default"
