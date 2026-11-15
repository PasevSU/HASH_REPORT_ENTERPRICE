# ChronoSeal Modern Integration DEV v7

- Added unique evidence-case directories to prevent collisions for runs started within one second.
- Changed final PDF publication to atomic, no-overwrite hard-link publication. Existing final PDFs are never replaced by a concurrent process. If the filesystem does not support this operation, the process fails closed.
- Randomized temporary publication paths to avoid collisions.
- Updated footer version label to DEV v7.
- All modes continue through the same Pipeline.run; SINGLE+PDF remains the special composition path.

## Release gate
NOT QUALIFIED. No real TSA end-to-end verification, full UI regression, or PDF visual qualification was performed for this build. The 7z donor archives have not been fully integrated.
