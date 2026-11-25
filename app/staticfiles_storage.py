"""Minifying static files storage.

collectstatic-time CSS/JS minification using pure-Python minifiers (no Node.js
required, so this works unchanged in the slim production Docker image). File
names are left untouched - cache-busting stays on the existing manual `?v=`
query-string scheme used in templates, so this only shrinks file contents.
"""
from django.contrib.staticfiles.storage import StaticFilesStorage
from django.core.files.base import ContentFile

import rcssmin
import rjsmin

MINIFIERS = {
    ".css": rcssmin.cssmin,
    ".js": rjsmin.jsmin,
}


class MinifiedStaticFilesStorage(StaticFilesStorage):
    """Shrink .css/.js files in place during `collectstatic`."""

    def post_process(self, paths, dry_run=False, **options):
        if dry_run:
            return

        for name in paths:
            if name.endswith((".min.css", ".min.js")):
                continue

            minify = next(
                (fn for ext, fn in MINIFIERS.items() if name.endswith(ext)),
                None,
            )
            if minify is None:
                continue

            try:
                with self.open(name) as source:
                    original = source.read().decode("utf-8")
                minified = minify(original)
            except (OSError, UnicodeDecodeError) as exc:
                yield name, name, exc
                continue

            if len(minified) >= len(original):
                yield name, name, False
                continue

            self.delete(name)
            self._save(name, ContentFile(minified.encode("utf-8")))
            yield name, name, True
