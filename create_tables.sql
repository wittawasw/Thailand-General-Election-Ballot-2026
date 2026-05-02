CREATE TABLE IF NOT EXISTS elections (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  year_be INTEGER NOT NULL,
  source_file TEXT,
  UNIQUE(name, year_be)
);

CREATE TABLE IF NOT EXISTS provinces (
  id INTEGER PRIMARY KEY,
  name_th TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS constituencies (
  id INTEGER PRIMARY KEY,
  election_id INTEGER NOT NULL,
  province_id INTEGER NOT NULL,
  constituency_no INTEGER NOT NULL,
  UNIQUE (election_id, province_id, constituency_no)
);

CREATE TABLE IF NOT EXISTS parties (
  id INTEGER PRIMARY KEY,
  name_th TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY,
  full_name_th TEXT NOT NULL,
  party_id INTEGER,
  UNIQUE (full_name_th, party_id)
);

CREATE TABLE IF NOT EXISTS constituency_results (
  id INTEGER PRIMARY KEY,
  election_id INTEGER NOT NULL,
  constituency_id INTEGER NOT NULL,
  candidate_id INTEGER NOT NULL,
  candidate_order INTEGER,
  votes INTEGER NOT NULL,
  result_percent REAL DEFAULT 100,
  UNIQUE (election_id, constituency_id, candidate_id, result_percent)
);

CREATE TABLE IF NOT EXISTS ballot_summaries (
  id INTEGER PRIMARY KEY,
  election_id INTEGER NOT NULL,
  constituency_id INTEGER NOT NULL,
  election_type TEXT NOT NULL,
  eligible_voters INTEGER,
  turnout_voters INTEGER,
  valid_ballots INTEGER,
  invalid_ballots INTEGER,
  no_vote_ballots INTEGER,
  result_percent REAL DEFAULT 100,
  UNIQUE (election_id, constituency_id, election_type, result_percent)
);

CREATE TABLE IF NOT EXISTS party_list_results (
  id INTEGER PRIMARY KEY,
  election_id INTEGER NOT NULL,
  constituency_id INTEGER NOT NULL,
  party_id INTEGER NOT NULL,
  votes INTEGER NOT NULL,
  result_percent REAL DEFAULT 100,
  UNIQUE (election_id, constituency_id, party_id, result_percent)
);

CREATE TABLE IF NOT EXISTS ballot_comparisons (
  id INTEGER PRIMARY KEY,
  election_id INTEGER NOT NULL,
  constituency_id INTEGER NOT NULL,
  election_type TEXT NOT NULL,
  turnout_94 INTEGER,
  turnout_100 INTEGER,
  turnout_diff INTEGER,
  valid_ballots_94 INTEGER,
  valid_ballots_100 INTEGER,
  valid_ballots_diff INTEGER,
  invalid_ballots_94 INTEGER,
  invalid_ballots_100 INTEGER,
  invalid_ballots_diff INTEGER,
  no_vote_ballots_94 INTEGER,
  no_vote_ballots_100 INTEGER,
  no_vote_ballots_diff INTEGER,
  note TEXT,
  UNIQUE (election_id, constituency_id, election_type)
);

CREATE TABLE IF NOT EXISTS source_rows (
  id INTEGER PRIMARY KEY,
  election_id INTEGER,
  sheet_name TEXT NOT NULL,
  row_number INTEGER NOT NULL,
  row_data TEXT NOT NULL,
  imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (sheet_name, row_number)
);

CREATE INDEX IF NOT EXISTS idx_constituencies_election_province_no
  ON constituencies(election_id, province_id, constituency_no);

CREATE INDEX IF NOT EXISTS idx_candidates_party
  ON candidates(party_id);

CREATE INDEX IF NOT EXISTS idx_constituency_results_constituency
  ON constituency_results(constituency_id);

CREATE INDEX IF NOT EXISTS idx_party_list_results_constituency
  ON party_list_results(constituency_id);

CREATE INDEX IF NOT EXISTS idx_party_list_results_party
  ON party_list_results(party_id);
