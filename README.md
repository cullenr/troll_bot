
## Setup

Set up the db:

```
# if the schema already exists and you want to lose it do this.
sudo -u postgres psql -tAc 'DROP SCHEMA troll CASCADE;' troll

# init a new db and run the HTTP interface
sudo -u postgres createdb troll
sudo -u postgres psql -v ON_ERROR_STOP=1 troll < main.sql
postgrest postgrest.conf
```
