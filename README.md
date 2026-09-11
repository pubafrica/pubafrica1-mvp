# PubAfrica — version persistante d’essai
Cette version conserve les utilisateurs, annonces et photos dans PostgreSQL/Supabase. Pour la phase gratuite, les photos de moins de 2 MB sont enregistrées directement avec l’annonce afin d’éviter les problèmes de permissions Storage. Avant une grande ouverture, migrer les images vers Storage objet.
