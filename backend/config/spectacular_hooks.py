def add_bearer_security(result, generator, request, public):
    """Injecte BearerAuth sur toutes les opérations qui ne déclarent pas de sécurité."""
    for path_item in result.get('paths', {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict) and 'security' not in operation:
                operation['security'] = [{'BearerAuth': []}]
    return result
