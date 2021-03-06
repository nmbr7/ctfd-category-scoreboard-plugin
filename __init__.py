import os
import datetime
import stream_chat
from flask import (
    render_template,
    jsonify,
    Blueprint,
    url_for,
    session,
    redirect,
    request,
    escape
)
from sqlalchemy.sql import or_

from CTFd.utils.helpers import get_errors, get_infos
from CTFd import utils, scoreboard
from CTFd.models import db, Solves, Challenges, Submissions, Teams, Users
from CTFd.plugins import override_template
from CTFd.utils.config import is_scoreboard_frozen, ctf_theme, is_users_mode
from CTFd.utils.config.visibility import challenges_visible, scores_visible
from CTFd.utils.dates import (
    ctf_started, ctftime, view_after_ctf, unix_time_to_utc
)
from CTFd.utils.user import is_admin, authed
from CTFd.utils.user import get_current_user
from CTFd.utils.decorators import authed_only
from CTFd.utils.decorators.visibility import (
    check_account_visibility,
    check_score_visibility,
)



def get_challenges():
    if not is_admin():
        if not ctftime():
            if view_after_ctf():
                pass
            else:
                return []
    if challenges_visible() and (ctf_started() or is_admin()):
        chals = db.session.query(
            Challenges.id,
            Challenges.name,
            Challenges.category
        ).filter(or_(Challenges.state != 'hidden', Challenges.state is None),Challenges.value != 1).all()

        jchals = []
        for x in chals:
            jchals.append({
                'id': x.id,
                'name': x.name,
                'category': x.category
            })

        # Sort into groups
        categories = set(map(lambda x: x['category'], jchals))
        return {"cat":sorted(list(categories))}
    return []

def load(app):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    template_path = os.path.join(dir_path, 'scoreboard-matrix.html')
    override_template('scoreboard.html', open(template_path).read())

    matrix = Blueprint('matrix', __name__, static_folder='static')
    app.register_blueprint(matrix, url_prefix='/matrix')

    def get_standings():
        standings = scoreboard.get_standings()
        # TODO faster lookup here
        jstandings = []
        for team in standings:
            teamid = team[0]
            solves = (db.session.query(Solves.challenge_id,Challenges.category,db.func.sum(Challenges.value),db.func.max(Solves.date))
                    .join(Challenges, Solves.challenge_id == Challenges.id)
                    .group_by(Challenges.category)
                    .filter(Solves.team_id == teamid)
                    .filter(Challenges.value != 1)
                    .filter(Challenges.value != 0)
            )
            
            challenge = (db.session.query(Challenges.category,db.func.sum(Challenges.value)).group_by(Challenges.category)).all()
            #print(team[2])
            chal_details = {}
            for i in challenge:
                chal_details.update({i[0]:i[1]})

            freeze = utils.get_config('freeze')
            if freeze:
                freeze = unix_time_to_utc(freeze)
                if teamid != session.get('id'):
                    #print(session.get('id'),teamid,freeze)
                    solves = solves.filter(Solves.date < freeze)

            solves = solves.all()
            score = []
            cat = get_challenges()["cat"]
            for i in solves:
                score.append({"id":i[0],"score":i[2],"cat":i[1],"date":i[3]})


            for i in cat:
                if i not in [j["cat"] for j in score]:
                    #score.append({"score":0,"cat":i,"date":datetime.datetime.utcfromtimestamp(111111111111)})
                    score.append({"score":0,"cat":i,"date": None,"id":-1})

            score = sorted(score, key = lambda i: i["cat"])

            
            maxscore = 0
            temp = []
            catfil = []
            count = 0

            for c,i in enumerate(score):
                if chal_details[i['cat']] == i['score']:
                    temp.append(i)
                    catfil.append(i['cat'])
                    maxscore += i['score']
                    count += 1

            if maxscore == 0:
                maxscore = {i["date"]:i["score"] for i in score}
                date = max(maxscore,key=maxscore.get)
                maxscore = maxscore[date]
                cat = {i["cat"]:i["score"] for i in score}
                cat = max(cat,key=cat.get)
                catfil.append(cat)
            else:
                date = sorted(temp, key = lambda i:i['date'],reverse=True)[0]['date']

            if date == None:
                continue
            
            # Check for the cat with the least date if there are multiple max values 


            
            jstandings.append({'teamid': team[0],'cat': catfil, 'solves': score, 'name': escape(team[2]),'date':date,'state':count, 'score': maxscore})
            jstandings = sorted(jstandings, key = lambda i: i["date"])
            #for i in jstandings:
            #    print(teamid,i['date'],i['score'])
            jstandings = sorted(jstandings, key = lambda i: i["score"],reverse=True)
            jstandings = sorted(jstandings, key = lambda i: i["state"],reverse=True)
            #print('next sort')
            #for i in jstandings:
            #    print(i['date'],i['score'])
        
        db.session.close()
        return jstandings

    
    def scoreboard_view():
        if scores_visible() and not authed():
            return redirect(url_for('auth.login', next=request.path))
        if not scores_visible():
            return render_template('scoreboard.html',
                                   errors=['Scores are currently hidden'])
        standings = get_standings()
        challenges = get_challenges()
        #for i in standings:
        #    print(i)
        return render_template(
                "scoreboard.html",
                standings=standings,
                challenges=challenges,
                mode='users' if is_users_mode() else 'teams',
                score_frozen=is_scoreboard_frozen(),
                theme=ctf_theme()
                )
    def scores():
        json = {'data': [],"succes": True}
        if scores_visible() and not authed():
            return redirect(url_for('auth.login', next=request.path))
        if not scores_visible():
            return jsonify(json)

        standings = get_standings()

        for i, x in enumerate(standings):
            score = ""
            for j in x['solves']:
                score += str(j['score'])+'</td><td class="chalmark">'
            score += str(x['score'])
            json['data'].append({"account_type": "team", 'pos': i + 1, "score": score,"name":escape(x['name']),"account_url":"/teams/", "member":[{
                "score":x['score'],
                "id":x['teamid'],
                "name":escape(x['name']),
                }]})

        return jsonify(json)

    # Route /api/v1/svoreboard/top/10 
    def scoreslist(count=10):
        json = {"success":True, "data": {}}
        if scores_visible() and not authed():
            return redirect(url_for('auth.login', next=request.path))
        if not scores_visible():
            return jsonify(json)

        standings = get_standings()

        for i, x in enumerate(standings[:10]):
            solves = (db.session.query(Solves.challenge_id,Challenges.value,Solves.date)
                    .join(Challenges, Solves.challenge_id == Challenges.id)
                    .filter(Challenges.category.in_(x['cat']))
                    .filter(Solves.team_id == x['teamid'])
            )
            
            freeze = utils.get_config('freeze')
            if freeze:
                freeze = unix_time_to_utc(freeze)
                if x['teamid'] != session.get('id'):
                    solves = solves.filter(Solves.date < freeze)
            solves = solves.all()
            #print(x['teamid'],'Stat Solve',solves)
            sol = []
            for s in solves:
                sol.append({'account_id':x['teamid'],'challenge_id':s[0],'date':s[2],'team_id':x['teamid'],'user_id':x['teamid'],'value':s[1]})
            
            sol = sorted(sol, key = lambda i: i["date"])
            json['data'].update({str(i + 1):{ 'id': x['teamid'], 'name': escape(x['name']), 'solves': sol}})
        return jsonify(json)
    
    def public(team_id):
        standings = get_standings()
        errors = get_errors()
        team = Teams.query.filter_by(id=team_id, banned=False, hidden=False).first_or_404()
        solves = team.get_solves()
        awards = team.get_awards()
        score = 0
        place = None
        for c,i in enumerate(standings):
            if i['teamid'] == team_id:
                place = c+1
                score = i['score']
                break

        if errors:
            return render_template("teams/public.html", team=team, errors=errors)

        return render_template(
            "teams/public.html",
            solves=solves,
            awards=awards,
            team=team,
            score=score,
            place=place,
            score_frozen=is_scoreboard_frozen(),
        )
    def private():
        standings = get_standings()
        user = get_current_user()
        if not user.team_id:
            return render_template("teams/team_enrollment.html")

        score = 0
        place = None
        team_id = user.team_id

        team = Teams.query.filter_by(id=team_id).first_or_404()
        solves = team.get_solves()
        awards = team.get_awards()

        for c,i in enumerate(standings):
            if i['teamid'] == team_id:
                place = c+1
                score = i['score']
                break

        return render_template(
            "teams/private.html",
            solves=solves,
            awards=awards,
            user=user,
            team=team,
            score=score,
            place=place,
            score_frozen=is_scoreboard_frozen(),
        )
    
    @app.route('/api/v1/current/user')
    @authed_only
    def currentuser():
        if not os.getenv("GETSTREAM_KEYS"):
            # Attempt to read the secret from the secret file
            # from CTFd/.get_stream_secrets
            # This will fail if the secret has not been written
            try:
                with open(".get_stream_secrets", "rb") as secret:
                    get_stream_key = secret.readlines()
            except (OSError, IOError):
                get_stream_key = None
        #print(get_stream_key)
        if get_stream_key is None or len(get_stream_key) < 2:
            print("Error: ********** getstream_key is None or is not in valid format ***********")
            return
        client = stream_chat.StreamChat(api_key=get_stream_key[0].strip(), api_secret=get_stream_key[1].strip())
        user = get_current_user()
        team = Teams.query.filter_by(id=user.team_id).first()
        if team:
            team_name = team.name
            team_id   = user.team_id
        else:
            team_name = "No_Team"
            team_id   = "No Team id"

        user_key = client.create_token(str(user.id))
        return jsonify({
            "current_username":user.name,
            "team_id":team_id,
            "team_name":team_name,
            "userid":user.id,
            "user_key":user_key,})

    app.view_functions['scoreboard.listing'] = scoreboard_view
    app.view_functions['teams.private'] = private
    app.view_functions['teams.public'] = public
    app.view_functions['scoreboard.score'] = scores
    app.view_functions['api.scoreboard_scoreboard_detail'] = scoreslist
    app.view_functions['api.scoreboard_scoreboard_list'] = scores
