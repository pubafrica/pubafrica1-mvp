# PubAfrica — version persistante
Cette version utilise DATABASE_URL pour PostgreSQL/Supabase. Elle conserve les utilisateurs, les annonces et la modération après redémarrage. Ajouter dans Render : DATABASE_URL et PUBAFRICA_SECRET. Pour un administrateur, créer un compte puis attribuer role=admin dans la table users pendant la phase de test.
