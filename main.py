import flask
import pandas as pd
import os
import logging
from google.cloud import storage
import random
from datetime import timezone
import datetime
import math
import io

#Uncomment below lines if using SQL

#import sqlalchemy
#import pymysql
#db_user = os.environ.get("DB_USER")
#db_pass = os.environ.get("DB_PASS")
#db_name = os.environ.get("DB_NAME")
#cloud_sql_connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")


CLOUD_STORAGE_BUCKET = os.environ.get('CLOUD_STORAGE_BUCKET')


#Defining Helper Functions

#Converts option from word to number
def choice_to_num(choice):
	if choice.lower() == 'rock':
		return 1
	elif choice.lower() == 'paper':
		return 2
	else:
		return 3

#Calculates computer move based on probabilities
def comp_prob_based(_decay_data, id_user):
	_probs = [0.333333, 0.333333, 0.333333]
	_decay_data_sub = _decay_data[_decay_data['user_id'] == id_user]
	_probs[0] += _decay_data_sub['Rock_c'].sum()
	_probs[1] += _decay_data_sub['Paper_c'].sum()
	_probs[2] += _decay_data_sub['Scizzors_c'].sum()

	if _probs[0] == _probs[1]:
		if _probs[0] == _probs[2]:
			return random.choice([1, 2, 3])
	else:
		temp = _probs.index(max(_probs)) + 1
		if temp == 1:
			return 2
		elif temp == 2:
			return 3
		else:
			return 1

#Updates player's probabilities based on results
def update_probs(data, decay_data, id_user):
	decay_factor = 0.95
	
	update_list = [0, 0, 0]
	temp_data = data[data['user_id'] == id_user]
	i = len(temp_data) - 1

	if temp_data['PlayerWin'].iloc[i] == 1:
		if temp_data['Player'].iloc[i] == 1:
			update_list = [0.05, -0.03, -0.02]

		elif temp_data['Player'].iloc[i] == 2:
			update_list = [-0.02, 0.05, -0.03]
		
		else:
			update_list = [-0.03, -0.02, 0.05]

	elif temp_data['PlayerWin'].iloc[i] == 2:
		if temp_data['Player'].iloc[i] == 1:
			update_list = [-0.06, 0.03, 0.03]

		elif temp_data['Player'].iloc[i] == 2:
			update_list = [0.03, -0.06, 0.03]

		else:
			update_list = [0.03, 0.03, -0.06]

	else:
		if temp_data['Player'].iloc[i] == 1:
			update_list = [-0.02, 0.01, 0.01]

		elif temp_data['Player'].iloc[i] == 2:
			update_list = [0.01, -0.02, 0.01]

		else:
			update_list = [0.01, 0.01, -0.02]

	user_decay_data = decay_data[decay_data['user_id'] == id_user] 

	user_decay_data['Rock_c'] = user_decay_data['Rock_c'] * 0.95
	user_decay_data['Paper_c'] = user_decay_data['Paper_c'] * 0.95
	user_decay_data['Scizzors_c'] = user_decay_data['Scizzors_c'] * 0.95

	decay_data[decay_data['user_id'] == id_user] = user_decay_data

	decay_data.loc[len(decay_data)] = [id_user, update_list[0], update_list[1], update_list[2]]
	
#Calculates winner
def winner(player, computer):
	if player == 1:
		if computer == 1:
			return 0
		elif computer == 2:
			return 2
		else:
			return 1

	elif player == 2:
		if computer == 1:
			return 1
		elif computer == 2:
			return 0
		else:
			return 2
	else:
		if computer == 1:
			return 2
		elif computer == 2:
			return 1
		else:
			return 0

#Plays entire game 1 time
def single_game(option, _user_id, _name):
	
	df = read_game_data()
	
	decayed_adjuster = read_prob_data()

	computer_choice = comp_prob_based(decayed_adjuster, _user_id)
	
	option = choice_to_num(option)

	winneris = winner(option, computer_choice)
	if winneris == 1:
		last_result = "You Win!"
	elif winneris == 2:
		last_result = "You LOSE"
	else:
		last_result = "Draw"

	
	df.loc[len(df)] = [_user_id, _name, option, computer_choice, winneris]

	temp_df = df[df['user_id'] == _user_id]
	draws = len(temp_df[temp_df['PlayerWin'] == 0])
	wins = len(temp_df[temp_df['PlayerWin'] == 1])
	loses = len(temp_df[temp_df['PlayerWin'] == 2])


	update_probs(df, decayed_adjuster, _user_id)

	save_game_data(df)
	save_prob_data(decayed_adjuster)
	
	return last_result, draws, wins, loses


app = flask.Flask(__name__)


#Home route: Creating new session
@app.route('/')
def root():
	dt = datetime.datetime.now() 
  
	utc_time = dt.replace(tzinfo = timezone.utc) 
	game_id = math.floor(utc_time.timestamp() * 10)
  
	return flask.render_template('index.html', game_id_api = game_id)


#API called by Client for playing a move from computer. Returns results, wins, loses, draws
@app.route('/api', methods=['POST', 'GET'])
def json_game_data():
	move = flask.request.args['move']
	user_id = int(flask.request.args['id'])
	name = flask.request.args['name']
	if flask.request.method == 'GET':
		_result, _draws, _wins, _loses = single_game(move, user_id, name)
		return {'wins': str(_wins),'loses': str(_loses), 'result': str(_result), 'draws': str(_draws)}, 200



if __name__ == '__main__':
	app.run(host = '127.0.0.1', port=8080, debug=True)


#Functions for saving and loading game data

def save_game_data(game_datum):
	gcs = storage.Client()
	bucket = gcs.get_bucket(CLOUD_STORAGE_BUCKET)
	
	game_datum_file = 'recorded_games.csv'
	
	blob = bucket.blob(game_datum_file)
	
	blob.cache_control = 'no-cache'
	s = io.StringIO()
	game_datum.to_csv(s, index=False)
	blob.upload_from_string(s.getvalue(), content_type='text/csv')
	


def save_prob_data(prob_datum):
	gcs = storage.Client()
	bucket = gcs.get_bucket(CLOUD_STORAGE_BUCKET)

	prob_datum_file = 'probs_update.csv'

	blob = bucket.blob(prob_datum_file)

	blob.cache_control = 'no-cache'
	s = io.StringIO()
	prob_datum.to_csv(s, index=False)
	blob.upload_from_string(s.getvalue(), content_type='text/csv')

	

def read_game_data():
	temp = pd.read_csv('https://storage.googleapis.com/game_prob_data/recorded_games.csv')
	#temp.drop(['Unnamed: 0'], axis=1, inplace=True)
	
	return temp

def read_prob_data():
	temp = pd.read_csv('https://storage.googleapis.com/game_prob_data/probs_update.csv')
	#temp.drop(['Unnamed: 0'], axis=1, inplace=True)

	return temp

