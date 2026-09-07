import os, sqlite3
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
app=Flask(__name__); app.secret_key=os.environ.get('PUBAFRICA_SECRET','change-me'); DB='pubafrica1.db'; UPLOAD='uploads'; os.makedirs(UPLOAD,exist_ok=True)
CSS='''<style>body{font:15px Arial;margin:0;background:#eefaff;color:#12364a}header,main,footer{max-width:900px;margin:auto;padding:20px}header{display:flex;justify-content:space-between}.brand{font-weight:bold;font-size:20px;color:#083b58}a{color:#087ea4;text-decoration:none;margin:5px}.btn,button{background:#ff8a3d;color:white;border:0;border-radius:8px;padding:10px 14px;font-weight:bold}input,textarea{display:block;width:100%;padding:11px;margin:6px 0 14px;border:1px solid #cfe5eb;border-radius:8px}textarea{min-height:100px}.hero,.panel,.card{background:white;padding:24px;border-radius:16px;margin:20px 0;box-shadow:0 8px 25px #2d9ab015}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card h3{color:#083b58}.muted{color:#698491}.alert{padding:12px;border-radius:8px;background:#e9fbf3;margin:10px 0}@media(max-width:650px){header{display:block}.grid{grid-template-columns:1fr}}</style>'''
BASE='''<!doctype html><html lang=fr><head><meta name=viewport content="width=device-width,initial-scale=1"><title>PubAfrica1</title>'''+CSS+'''</head><body><header><a class=brand href="/">✦ pubafrica1</a><nav><a href="/">Explorer</a>{% if session.get("uid") %}<a href="/dashboard">Mon espace</a><a href="/publish">Publier</a><a href="/logout">Sortir</a>{% else %}<a href="/login">Connexion</a><a href="/register">Inscription</a>{% endif %}</nav></header><main>{% for m in get_flashed_messages() %}<div class=alert>{{m}}</div>{% endfor %}{% block content %}{% endblock %}</main><footer>PubAfrica1 · Gratuit pour commencer</footer></body></html>'''
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.executescript('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,password TEXT,role TEXT DEFAULT "member");CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY,user_id INTEGER,title TEXT,description TEXT,category TEXT,location TEXT,price TEXT,status TEXT DEFAULT "pending"); CREATE TABLE IF NOT EXISTS images(id INTEGER PRIMARY KEY,listing_id INTEGER,file_name TEXT);'); c.execute('INSERT OR IGNORE INTO users(name,email,password,role) VALUES(?,?,?,?)',('Administrateur','admin@pubafrica1.test',generate_password_hash(os.environ.get('ADMIN_PASSWORD','ChangeAdmin123!')),'admin')); c.commit(); return c
def page(body,**ctx): return render_template_string(BASE.replace('{% block content %}{% endblock %}',body),**ctx)
def auth(f):
 @wraps(f)
 def w(*a,**k):
  if not session.get('uid'): return redirect('/login')
  return f(*a,**k)
 return w
@app.route('/')
def home():
 q=request.args.get('q',''); c=db(); items=c.execute("SELECT l.*,u.name FROM listings l JOIN users u ON u.id=l.user_id WHERE l.status='published' AND (l.title LIKE ? OR l.description LIKE ?) ORDER BY l.id DESC",(f'%{q}%',f'%{q}%')).fetchall(); return page('''<section class=hero><p class=muted>Le marché africain en mouvement</p><h1>Trouvez. Publiez. Développez.</h1><p>Inscription et publication gratuites.</p><form><input name=q placeholder="Rechercher un produit ou service" value="{{q}}"><button>Rechercher</button></form></section><h2>Annonces</h2><div class=grid>{% for x in items %}<a class=card href="/listing/{{x.id}}"><h3>{{x.title}}</h3><p>{{x.description[:100]}}</p><small>{{x.category}} · {{x.location}}</small><b>{{x.price or "Prix sur demande"}}</b></a>{% else %}<p>Aucune annonce publiée.</p>{% endfor %}</div>''',items=items,q=q)
@app.route('/register',methods=['GET','POST'])
def register():
 if request.method=='POST':
  try:
   c=db(); cur=c.execute('INSERT INTO users(name,email,password) VALUES(?,?,?)',(request.form['name'],request.form['email'].lower(),generate_password_hash(request.form['password']))); c.commit(); session['uid']=cur.lastrowid; session['name']=request.form['name']; return redirect('/dashboard')
  except sqlite3.IntegrityError: flash('Cet e-mail existe déjà.')
 return page('''<div class=panel><h1>Créer un compte</h1><form method=post><label>Nom<input name=name required></label><label>E-mail<input name=email type=email required></label><label>Mot de passe<input name=password type=password minlength=6 required></label><button>Créer mon compte</button></form></div>''')
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  u=db().execute('SELECT * FROM users WHERE email=?',(request.form['email'].lower(),)).fetchone()
  if u and check_password_hash(u['password'],request.form['password']): session['uid']=u['id'];session['name']=u['name'];session['role']=u['role'];return redirect('/admin' if u['role']=='admin' else '/dashboard')
  flash('Identifiants incorrects.')
 return page('''<div class=panel><h1>Connexion</h1><form method=post><input name=email type=email placeholder="E-mail" required><input name=password type=password placeholder="Mot de passe" required><button>Se connecter</button></form></div>''')
@app.route('/admin')
@auth
def admin():
 if session.get('role')!='admin': return 'Accès réservé à l’administrateur',403
 pending=db().execute("SELECT l.*,u.name FROM listings l JOIN users u ON u.id=l.user_id WHERE l.status='pending' ORDER BY l.id DESC").fetchall()
 return page('''<div class=panel><p class=muted>Administration PubAfrica1</p><h1>Contrôle des annonces</h1>{% for x in pending %}<div class=card><h3>{{x.title}}</h3><p>{{x.description}}</p><small>{{x.name}} · {{x.category}} · {{x.location}}</small><form method=post action="/admin/listing/{{x.id}}/published"><button>Valider</button></form><form method=post action="/admin/listing/{{x.id}}/rejected"><button>Refuser</button></form></div>{% else %}<p>Aucune annonce en attente.</p>{% endfor %}</div>''',pending=pending)
@app.route('/admin/listing/<int:i>/<status>',methods=['POST'])
@auth
def admin_listing(i,status):
 if session.get('role')!='admin' or status not in ('published','rejected'): return 'Accès refusé',403
 c=db(); c.execute('UPDATE listings SET status=? WHERE id=?',(status,i)); c.commit(); return redirect('/admin')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')
@app.route('/dashboard')
@auth
def dashboard(): items=db().execute('SELECT * FROM listings WHERE user_id=?',(session['uid'],)).fetchall(); return page('''<div class=panel><h1>Bonjour {{session.name}}</h1><a class=btn href=/publish>Nouvelle annonce</a><h2>Mes annonces</h2>{% for x in items %}<div class=card><b>{{x.title}}</b><p>{{x.status}}</p></div>{% else %}<p>Aucune annonce.</p>{% endfor %}</div>''',items=items)
@app.route('/publish',methods=['GET','POST'])
@auth
def publish():
 if request.method=='POST':
  c=db();cur=c.execute('INSERT INTO listings(user_id,title,description,category,location,price) VALUES(?,?,?,?,?,?)',(session['uid'],request.form['title'],request.form['description'],request.form['category'],request.form['location'],request.form['price'])); lid=cur.lastrowid
  for f in request.files.getlist('images'):
   if f and f.filename and f.filename.lower().rsplit('.',1)[-1] in ('jpg','jpeg','png','webp'):
    fn=f'{lid}_{secure_filename(f.filename)}'; f.save(os.path.join(UPLOAD,fn)); c.execute('INSERT INTO images(listing_id,file_name) VALUES(?,?)',(lid,fn))
  c.commit();flash('Annonce envoyée pour validation.');return redirect('/dashboard')
 return page('''<div class=panel><h1>Publier gratuitement</h1><form method=post enctype="multipart/form-data"><input name=title placeholder="Titre" required><textarea name=description placeholder="Description" required></textarea><input name=category placeholder="Catégorie" required><input name=location placeholder="Pays / ville" required><input name=price placeholder="Prix"><label>Photos<input type=file name=images multiple accept="image/png,image/jpeg,image/webp"></label><button>Envoyer</button></form></div>''')
@app.route('/listing/<int:i>')
def listing(i):
 x=db().execute("SELECT l.*,u.name FROM listings l JOIN users u ON u.id=l.user_id WHERE l.id=? AND l.status='published'",(i,)).fetchone(); imgs=db().execute('SELECT * FROM images WHERE listing_id=?',(i,)).fetchall(); return page('''<div class=panel>{% if x %}<p class=muted>{{x.category}} · {{x.location}}</p><h1>{{x.title}}</h1>{% for im in imgs %}<img style="max-width:180px;margin:5px;border-radius:10px" src="/uploads/{{im.file_name}}">{% endfor %}<p>{{x.description}}</p><h2>{{x.price or 'Prix sur demande'}}</h2><p>Annonceur : {{x.name}}</p>{% else %}<h1>Annonce introuvable</h1>{% endif %}</div>''',x=x,imgs=imgs)
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',8000)))
