"""Accès facultatif aux coffres d'identifiants du système d'exploitation."""

SERVICE = 'Foodvisor Exporter'
SECURE_BACKENDS = {
    'keyring.backends.SecretService',
    'keyring.backends.Windows',
    'keyring.backends.kwallet',
    'keyring.backends.libsecret',
    'keyring.backends.macOS',
}


def secure_keyring():
    """Retourne keyring seulement si tous les fournisseurs actifs sont connus."""
    try:
        import keyring
        backend = keyring.get_keyring()
        backends = getattr(backend, 'backends', [backend])
        if not backends or any(type(item).__module__ not in SECURE_BACKENDS for item in backends):
            return None
        return keyring
    except Exception:
        return None


def get_password(mail):
    backend = secure_keyring()
    if backend is None:
        raise RuntimeError('Aucun coffre d’identifiants compatible disponible.')
    return backend.get_password(SERVICE, mail)


def set_password(mail, password):
    backend = secure_keyring()
    if backend is None:
        raise RuntimeError('Aucun coffre d’identifiants compatible disponible.')
    backend.set_password(SERVICE, mail, password)


def delete_password(mail):
    backend = secure_keyring()
    if backend is None:
        raise RuntimeError('Aucun coffre d’identifiants compatible disponible.')
    backend.delete_password(SERVICE, mail)
