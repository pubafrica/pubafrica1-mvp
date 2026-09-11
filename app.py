import os
import uuid
import base64
from functools import wraps
from flask import Flask, request, redirect, session, flash, render_template_string, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2
import requests
from psycopg2.extras import RealDictCursor

app=Flask(__name__)
app.secret_key=os.environ.get('PUBAFRICA_SECRET','change-this-secret-before-production')
DATABASE_URL=os.environ['DATABASE_URL']
SUPABASE_URL=os.environ.get('SUPABASE_URL','')
SUPABASE_SERVICE_KEY=os.environ.get('SUPABASE_SERVICE_KEY','')
UPLOAD='uploads'; os.makedirs(UPLOAD,exist_ok=True)
CSS='''<style>body{font:15px Arial;margin:0;background:#eefaff;color:#12364a}header,main,footer{max-width:960px;margin:auto;padding:20px}header{display:flex;justify-content:space-between}.brand{font-weight:bold;font-size:20px;color:#083b58}a{color:#087ea4;text-decoration:none;margin:5px}.btn,button{background:#ff8a3d;color:white;border:0;border-radius:8px;padding:10px 14px;font-weight:bold}input,textarea{display:block;width:100%;padding:11px;margin:6px 0 14px;border:1px solid #cfe5eb;border-radius:8px}textarea{min-height:100px}.hero,.panel,.card{background:white;padding:24px;border-radius:16px;margin:20px 0;box-shadow:0 8px 25px #2d9ab015}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card h3{color:#083b58}.muted{color:#698491}.alert{padding:12px;border-radius:8px;background:#e9fbf3;margin:10px 0}.photos img{max-width:180px;margin:5px;border-radius:10px}@media(max-width:650px){header{display:block}.grid{grid-template-columns:1fr}}</style>'''
BASE='''<!doctype html><html lang=fr><head><meta name=viewport content="width=device-width,initial-scale=1"><title>PubAfrica</title>'''+CSS+'''</head><body><header><a class=brand href="/">✦ PubAfrica</a><nav><a href="/">Explorer</a>{% if session.get("uid") %}<a href="/dashboard">Mon espace</a><a href="/publish">Publier</a>{% if session.get("role")=="admin" %}<a href="/admin">Administration</a>{% endif %}<a href="/logout">Sortir</a>{% else %}<a href="/login">Connexion</a><a href="/register">Inscription</a>{% endif %}</nav></header><main>{% for m in get_flashed_messages() %}<div class=alert>{{m}}</div>{% endfor %}{% block content %}{% endblock %}</main><footer>PubAfrica · Gratuit pendant la phase d’essai · Appel/WhatsApp : 0196482016 · 0195209533 · pubafrica1@gmail.com</footer></body></html>'''
def page(body,**ctx): return render_template_string(BASE.replace('{% block content %}{% endblock %}',body),**ctx)
def conn(): return psycopg2.connect(DATABASE_URL,sslmode='require',cursor_factory=RealDictCursor)
def init_db():
 c=conn(); cur=c.cursor(); cur.execute('''create table if not exists users(id bigserial primary key,name text not null,email text unique,password_hash text not null,role text not null default 'member',created_at timestamptz default now());alter table users alter column email drop not null;alter table users add column if not exists phone text unique;create table if not exists listings(id bigserial primary key,user_id bigint references users(id) on delete cascade,title text not null,description text not null,category text not null,location text not null,price text,status text not null default 'pending',created_at timestamptz default now());create table if not exists listing_images(id bigserial primary key,listing_id bigint references listings(id) on delete cascade,file_url text not null,created_at timestamptz default now());create table if not exists inquiries(id bigserial primary key,listing_id bigint references listings(id) on delete cascade,sender_name text not null,sender_contact text not null,message text not null,created_at timestamptz default now());'''); c.commit(); cur.close(); c.close()
try: init_db()
except Exception: pass

def ensure_admin():
    email=os.environ.get('ADMIN_EMAIL'); password=os.environ.get('ADMIN_PASSWORD')
    if not email or not password: return
    c=conn(); cur=c.cursor(); cur.execute('select id from users where email=%s',(email.lower(),))
    if cur.fetchone(): cur.execute('update users set role=\'admin\' where email=%s',(email.lower(),))
    else: cur.execute('insert into users(name,email,password_hash,role) values(%s,%s,%s,\'admin\')',('Administrateur',email.lower(),generate_password_hash(password)))
    c.commit(); c.close()
try: ensure_admin()
except Exception: pass
def auth(f):
 @wraps(f)
 def w(*a,**k):
  if not session.get('uid'): return redirect('/login')
  return f(*a,**k)
 return w

def admin(f):
 @wraps(f)
 def w(*a,**k):
  if session.get('role')!='admin': return 'Accès administrateur refusé',403
  return f(*a,**k)
 return w
@app.route('/')
def home():
 q=request.args.get('q',''); c=conn(); cur=c.cursor(); cur.execute("select l.*,u.name from listings l join users u on u.id=l.user_id where l.status='published' and (l.title ilike %s or l.description ilike %s) order by l.id desc",(f'%{q}%',f'%{q}%')); items=cur.fetchall(); c.close(); return page('''<section class=hero><p class=muted>Le marché africain en mouvement</p><h1>Trouvez. Publiez. Développez.</h1><form><input name=q value="{{q}}" placeholder="Rechercher un produit ou service"><button>Rechercher</button></form></section><h2>Annonces</h2><div class=grid>{% for x in items %}<a class=card href="/listing/{{x.id}}"><h3>{{x.title}}</h3><p>{{x.description[:100]}}</p><small>{{x.category}} · {{x.location}}</small><b>{{x.price or 'Prix sur demande'}}</b></a>{% else %}<p>Aucune annonce publiée.</p>{% endfor %}</div>''',items=items,q=q)
@app.route('/register',methods=['GET','POST'])
def register():
 if request.method=='POST':
  try:
   contact=request.form['contact'].strip(); email=contact.lower() if '@' in contact else None; phone=None if email else contact
   c=conn();cur=c.cursor();cur.execute('insert into users(name,email,phone,password_hash) values(%s,%s,%s,%s) returning id',(request.form['name'],email,phone,generate_password_hash(request.form['password']))); uid=cur.fetchone()['id'];c.commit();c.close();session.update(uid=uid,name=request.form['name'],role='member');return redirect('/dashboard')
  except Exception: flash('Cet e-mail ou ce numéro est déjà utilisé, ou les données sont invalides.')
 return page('''<div class=panel><h1>Créer un compte</h1><p class=muted>Choisis un e-mail ou un numéro de téléphone.</p><form method=post><input name=name placeholder="Nom complet" required><input name=contact placeholder="E-mail ou numéro de téléphone" required><input name=password type=password minlength=6 placeholder="Mot de passe" required><button>Créer mon compte</button></form></div>''')
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  contact=request.form['contact'].strip(); c=conn();cur=c.cursor();cur.execute('select * from users where email=%s or phone=%s',(contact.lower(),contact));u=cur.fetchone();c.close()
  if u and check_password_hash(u['password_hash'],request.form['password']): session.update(uid=u['id'],name=u['name'],role=u['role']);return redirect('/admin' if u['role']=='admin' else '/dashboard')
  flash('Identifiants incorrects.')
 return page('''<div class=panel><h1>Connexion</h1><form method=post><input name=contact placeholder="E-mail ou numéro de téléphone" required><input name=password type=password placeholder="Mot de passe" required><button>Se connecter</button></form></div>''')
@app.route('/logout')
def logout(): session.clear();return redirect('/')
@app.route('/dashboard')
@auth
def dashboard():
 c=conn();cur=c.cursor();cur.execute('select * from listings where user_id=%s order by id desc',(session['uid'],));items=cur.fetchall();c.close();return page('''<div class=panel><h1>Bonjour {{session.name}}</h1><a class=btn href=/publish>Nouvelle annonce</a><h2>Mes annonces</h2>{% for x in items %}<div class=card><b>{{x.title}}</b><p>Statut : {{x.status}}</p><form method=post action="/delete-listing/{{x.id}}"><button type=submit>Supprimer</button></form></div>{% else %}<p>Aucune annonce.</p>{% endfor %}</div>''',items=items)
@app.route('/publish',methods=['GET','POST'])
@auth
def publish():
 if request.method=='POST':
  c=conn();cur=c.cursor();cur.execute('insert into listings(user_id,title,description,category,location,price) values(%s,%s,%s,%s,%s,%s) returning id',(session['uid'],request.form['title'],request.form['description'],request.form['category'],request.form['location'],request.form['price']));lid=cur.fetchone()['id']
  photo_count=0
  for f in request.files.getlist('images'):
   if f and f.filename and (f.mimetype or '').startswith('image/'):
    data=f.read()
    if len(data)>2_000_000: raise RuntimeError('Photo too large; maximum 2 MB')
    url=f'data:{f.mimetype};base64,'+base64.b64encode(data).decode('ascii')
    cur.execute('insert into listing_images(listing_id,file_url) values(%s,%s)',(lid,url)); photo_count += 1
  c.commit();c.close();flash(f'Annonce envoyée pour validation avec {photo_count} photo(s).');return redirect('/dashboard')
 return page('''<div class=panel><h1>Publier gratuitement</h1><form method=post enctype="multipart/form-data"><input name=title placeholder="Titre" required><textarea name=description placeholder="Description" required></textarea><input name=category placeholder="Catégorie" required><input name=location placeholder="Pays / ville" required><input name=price placeholder="Prix"><label>Photos<input type=file name=images multiple accept="image/*"></label><button>Envoyer</button></form></div>''')
@app.route('/admin')
@admin
def admin_page():
 c=conn();cur=c.cursor();cur.execute("select l.*,u.name from listings l join users u on u.id=l.user_id where l.status='pending' order by l.id desc");items=cur.fetchall();c.close();return page('''<div class=panel><p class=muted>Administration PubAfrica</p><h1>Annonces à vérifier</h1>{% for x in items %}<div class=card><h3>{{x.title}}</h3><p>{{x.description}}</p><small>{{x.name}} · {{x.category}} · {{x.location}}</small><form method=post action="/admin/listing/{{x.id}}/published"><button>Valider</button></form><form method=post action="/admin/listing/{{x.id}}/rejected"><button>Refuser</button></form><form method=post action="/delete-listing/{{x.id}}"><button>Supprimer</button></form></div>{% else %}<p>Aucune annonce en attente.</p>{% endfor %}</div>''',items=items)
@app.route('/admin/listing/<int:i>/<status>',methods=['POST'])
@admin
def moderate(i,status):
 if status not in ('published','rejected'): abort(400)
 c=conn();cur=c.cursor();cur.execute('update listings set status=%s where id=%s',(status,i));c.commit();c.close();return redirect('/admin')
@app.route('/delete-listing/<int:i>',methods=['POST'])
@auth
def delete_listing(i):
 c=conn();cur=c.cursor();
 if session.get('role')=='admin': cur.execute('delete from listings where id=%s',(i,))
 else: cur.execute('delete from listings where id=%s and user_id=%s',(i,session['uid']))
 c.commit();c.close();flash('Annonce supprimée.');return redirect('/admin' if session.get('role')=='admin' else '/dashboard')

@app.route('/contact/<int:i>',methods=['GET','POST'])
def contact(i):
 if request.method=='POST':
  c=conn();cur=c.cursor();cur.execute('insert into inquiries(listing_id,sender_name,sender_contact,message) values(%s,%s,%s,%s)',(i,request.form['sender_name'],request.form['sender_contact'],request.form['message']));c.commit();c.close();flash('Votre message a été enregistré.');return redirect(f'/listing/{i}')
 return page('''<div class=panel><h1>Écrire à l’annonceur</h1><form method=post><input name=sender_name placeholder="Votre nom" required><input name=sender_contact placeholder="Votre e-mail ou numéro" required><textarea name=message placeholder="Écrivez votre demande de devis ou votre question" required></textarea><button>Envoyer le message</button></form></div>''')

@app.route('/listing/<int:i>')
def listing(i):
 c=conn();cur=c.cursor();cur.execute("select l.*,u.name,u.email,u.phone from listings l join users u on u.id=l.user_id where l.id=%s and l.status='published'",(i,));x=cur.fetchone();cur.execute('select * from listing_images where listing_id=%s',(i,));imgs=cur.fetchall();c.close();return page('''<div class=panel>{% if x %}<p class=muted>{{x.category}} · {{x.location}}</p><h1>{{x.title}}</h1><div class=photos>{% for im in imgs %}<img src="{{im.file_url}}" alt="Photo de l’annonce">{% endfor %}</div><p>{{x.description}}</p><h2>{{x.price or 'Prix sur demande'}}</h2><p>Annonceur : {{x.name}}</p><div class=contact><h2>Contacter l’annonceur</h2><a class=btn href="/contact/{{x.id}}">Écrire un message</a>{% if x.phone %}<a class=btn href="tel:{{x.phone}}">Appeler</a><a class=btn href="https://wa.me/{{x.phone}}">WhatsApp</a>{% endif %}{% if x.email %}<a class=btn href="mailto:{{x.email}}?subject=Demande%20d%27informations%20sur%20{{x.title}}">E-mail</a>{% endif %}</div>{% else %}<h1>Annonce introuvable</h1>{% endif %}</div>''',x=x,imgs=imgs)
@app.route('/health')
def health(): return {'status':'ok','service':'PubAfrica'}
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',8000)))
