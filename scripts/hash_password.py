"""Genera un hash bcrypt para crear manualmente el primer usuario admin en Supabase.

Uso:
    python scripts/hash_password.py "mi-contraseña-temporal"

Copia el hash impreso y úsalo en un INSERT sobre la tabla `users`, por ejemplo:
    insert into users (email, name, password_hash, role, active)
    values ('tu_correo@empresa.com', 'Tu Nombre', '<hash pegado aquí>', 'admin', true);
"""

import argparse
import bcrypt


def main():
    parser = argparse.ArgumentParser(description="Genera un hash bcrypt para la tabla users.")
    parser.add_argument("password", help="Contraseña en texto plano a hashear")
    args = parser.parse_args()

    hashed = bcrypt.hashpw(args.password.encode("utf-8"), bcrypt.gensalt())
    print(hashed.decode("utf-8"))


if __name__ == "__main__":
    main()
