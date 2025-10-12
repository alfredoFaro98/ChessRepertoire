from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Permette di usare dict[key] nei template"""
    if dictionary is None:
        return None
    return dictionary.get(key)
