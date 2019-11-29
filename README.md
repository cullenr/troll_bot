## Setup

Set up the environment:

```
pipenv shell
pipenv install
```

Set up the db:

```shell
# if the schema already exists and you want to lose it do this.
sudo -u postgres psql -tAc 'DROP SCHEMA troll CASCADE;' troll

# init a new db and run the HTTP interface
sudo -u postgres createdb troll
sudo -u postgres psql -v ON_ERROR_STOP=1 troll < main.sql
postgrest postgrest.conf
```

Add users from pictures:

```
pipenv run python add-user.py ~/loft/me.jpg 'Dorian Grey'
```

Run the scanner:

```
pipenv run python main.py
```
