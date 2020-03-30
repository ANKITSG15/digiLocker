from flask import Flask, escape, request, session, redirect, url_for, jsonify, flash
from flask import render_template
from utils import *
import jwt
import random, os, string
import datetime
from functools import wraps
import settings
import hashlib
from flask_mail import Mail
from werkzeug.utils import secure_filename
# from werkzeug import secure_filename
import dropbox


ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', "docx"])
app = Flask(__name__)
app.config['SECRET_KEY'] = b'OCML3BRawWEUeaxcuKHLpw'
app.config.from_object(settings)
mail = Mail(app)
dropbox_ = dropbox.Dropbox(app.config["DROPBOX_ACCESS_TOKEN"])

# API_KEY = 'your_api_key'
# dbx_client = dropbox.Dropbox(API_KEY)


def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if 'x-access-tokens' in session.keys():
            token = session.get('x-access-tokens')
            try:
                data = jwt.decode(token, app.config["SECRET_KEY"])
                user_address = session.get("user_address")
                return f(user_address, *args, **kwargs)
            except Exception as e:
                print(e)
                return redirect("/")

        return redirect("/")
    return decorator

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
@token_required
def dashboard(user_address = None):
    return render_template("dashboard.html", user_address = user_address)

@app.route("/registration")
@token_required
def registration(user_address):
    return render_template("registration.html", user_address = user_address)



def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/dashboard/upload/doc', methods=['GET', 'POST'])
@token_required
def upload_file(user_address):
    if request.method == 'POST':

        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        if 'total_doc' not in request.form:
            flash('No file part')
            return redirect(request.url)
        
        total_doc = request.form["total_doc"]
        file_name = request.form["filename"]
        file = request.files['file']

        try:
            savepath = f"{user_address}/{file.filename}"
            dropbox_.files_upload(file.read(), savepath)
        except Exception as e:
            print(e)

        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('uploaded_file',
                                    filename=filename))
    return render_template("upload_doc.html", user_address=user_address)


@app.route("/api/register/metamask", methods = ['POST'])
def registration_postapi():
    email = request.form.get("email")
    master_key = request.form.get("master_key")
    user_address = request.form.get("user_address")
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")

    pu, pr = generateRSAKeypair()
    msg = prepareMailMsg(f"{first_name} {last_name}", email, user_address, pu, pr, master_key)
    mail.send(msg)
    mkey_digest = hashlib.sha256(master_key.strip().encode()).hexdigest()

    if True:
        return {
            'success': True, 
            'redirect_url': "/dashboard",
            "master_key_hash": mkey_digest,
            'error': "Address verification done",
            "pu": pu.decode()
        }
    else:
        return {
            'success': False, 
            'redirect_url': "/",
            'error': "Address verification failed"
        }


@app.route("/api/login/metamask", methods = ['GET'])
def login_api():
    urandomToken = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for i in range(32))
    token = jwt.encode({
        'exp' : datetime.datetime.utcnow() + datetime.timedelta(minutes=60),
        'token': urandomToken
        }, 
        app.config['SECRET_KEY']
    ).decode("utf-8")
    session['x-access-tokens'] = token
    return jsonify({"data": token, })

@app.route("/api/login/metamask", methods = ['POST'])
def login_postapi():
    token = session.get('x-access-tokens')
    if not token:
        return {'error': "No login token in session, please request token again by sending GET request to this url",
                'success': False}
    else:
        # session.pop("x-access-tokens", None)
        signature = request.form.get("signature")
        address = request.form.get("address")
        is_registered = request.form.get("newuser")
        session["user_address"] = address
        recovered_addr = recover_to_addr(token, signature)
        if address != recovered_addr:
            return {
                'success': False, 
                'redirect_url': "/",
                'error': "Address verification failed"
            }
        else:
            if is_registered == "false":
                return {'success': True, 'redirect_url': "/registration"}
            else:
                return {'success': True, 'redirect_url': "/dashboard"}


@app.route("/api/user/accesskey", methods = ['POST'])
@token_required
def comparehash_digest(user_address):
    try:
        master_key, mkeydigest = request.form['master_key'], request.form['mkeydigest']
        mkey_digest_new = hashlib.sha256(master_key.strip().encode()).hexdigest()

        if "0x" + mkey_digest_new == mkeydigest:
            return jsonify({"valid": True, 'success': True})  
        else:
            return jsonify({"valid": False, 'success': True})        
    except Exception as e:
        print(e)
        return jsonify({'success': False})   


@app.route("/api/logout/metamask", methods = ['GET'])
@token_required
def logout(user_address3):
    print("logout")
    session.pop("x-access-tokens", None)
    session.pop("user_address", None)
    return {'success': True, 'redirect_url': "/"}


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
    # app.run(host="172.18.16.108", debug=True)