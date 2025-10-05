"""
Pagination utility for the Asset Management System
"""
from flask import request
from models import SystemSetting


def get_items_per_page(user=None):
    """
    Get the number of items per page for pagination.
    Priority: User preference > System default > Hardcoded default (20)

    Args:
        user: User object (optional)

    Returns:
        int: Number of items per page
    """
    # Check user preference first
    if user and user.items_per_page:
        return user.items_per_page

    # Fall back to system default
    system_default = SystemSetting.query.filter_by(key='default_items_per_page').first()
    if system_default and system_default.value:
        try:
            return int(system_default.value)
        except (ValueError, TypeError):
            pass

    # Hardcoded default
    return 20


def get_pagination_params(user=None):
    """
    Get pagination parameters from request arguments.

    Args:
        user: User object (optional)

    Returns:
        tuple: (page, per_page) where page is 1-indexed
    """
    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(request.args.get('per_page', 0))
        if per_page < 1:
            per_page = get_items_per_page(user)
    except (ValueError, TypeError):
        per_page = get_items_per_page(user)

    # Enforce maximum per_page to prevent abuse
    max_per_page = 100
    if per_page > max_per_page:
        per_page = max_per_page

    return page, per_page


def get_sort_params():
    """
    Get sorting parameters from request arguments.

    Returns:
        tuple: (sort_by, sort_order) where sort_order is 'asc' or 'desc'
    """
    sort_by = request.args.get('sort_by', '')
    sort_order = request.args.get('sort_order', 'asc').lower()

    # Validate sort_order
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'

    return sort_by, sort_order


def paginate_query(query, user=None, page=None, per_page=None):
    """
    Paginate a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        user: User object (optional)
        page: Page number (optional, will read from request if not provided)
        per_page: Items per page (optional, will use user/system default if not provided)

    Returns:
        dict: Pagination result with items, page info, and metadata
    """
    if page is None or per_page is None:
        page, per_page = get_pagination_params(user)

    # Get total count
    total = query.count()

    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 1

    # Ensure page is within valid range
    if page > total_pages and total_pages > 0:
        page = total_pages

    # Calculate offset
    offset = (page - 1) * per_page

    # Get items for current page
    items = query.offset(offset).limit(per_page).all()

    return {
        'items': items,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None,
    }


def create_pagination_response(pagination_result, item_serializer=None):
    """
    Create a standardized pagination response.

    Args:
        pagination_result: Result from paginate_query()
        item_serializer: Function to serialize each item (e.g., lambda x: x.to_dict())

    Returns:
        dict: Standardized pagination response
    """
    items = pagination_result['items']

    if item_serializer:
        items = [item_serializer(item) for item in items]

    return {
        'items': items,
        'pagination': {
            'page': pagination_result['page'],
            'per_page': pagination_result['per_page'],
            'total': pagination_result['total'],
            'total_pages': pagination_result['total_pages'],
            'has_prev': pagination_result['has_prev'],
            'has_next': pagination_result['has_next'],
            'prev_page': pagination_result['prev_page'],
            'next_page': pagination_result['next_page'],
        }
    }
