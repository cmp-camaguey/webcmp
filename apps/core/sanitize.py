"""HTML sanitization for dashboard-editable rich content."""

from __future__ import annotations

import nh3

ALLOWED_TAGS = {
    'a',
    'blockquote',
    'br',
    'code',
    'div',
    'em',
    'h3',
    'h4',
    'h5',
    'h6',
    'hr',
    'li',
    'ol',
    'p',
    'pre',
    'span',
    'strong',
    'sub',
    'sup',
    'table',
    'tbody',
    'td',
    'th',
    'thead',
    'tr',
    'u',
    'ul',
}

ALLOWED_ATTRIBUTES = {
    '*': {'class', 'id'},
    'a': {'href', 'target', 'title'},
    'td': {'colspan', 'rowspan'},
    'th': {'colspan', 'rowspan', 'scope'},
}

ALLOWED_URL_SCHEMES = {'http', 'https', 'mailto', 'tel'}

LINK_REL = 'noopener noreferrer'


def sanitize_html(value: str) -> str:
    """Return sanitized HTML safe for rendering in institutional pages."""
    if not value:
        return ''
    cleaned = nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel=LINK_REL,
    )
    return cleaned.strip()
