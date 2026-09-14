# Demo seed data

These are created programmatically on first run by `backend/database/seed.py`
(not hand-edited JSON, since the teacher password needs to be hashed):

- One demo teacher account:
  - Teacher ID: `T-1001`
  - Password: `demo1234`
  - Name: Mrs. Hembrom
  - Class: 3, Subject: Environmental Studies

- One demo lesson: "Parts of a Plant" (Hindi -> Santhali), linked to the
  `worksheet-parts-of-a-plant` worksheet and the flashcards in
  `data/flashcards/seed.json`.

- A handful of realistic worksheet submissions for Class 3 so the Assessment
  & Analytics screen has something to show immediately (average score,
  completion count, and one deliberately weak concept: "flower").

Run `python -m backend.database.seed` (or just start the app — it seeds
automatically if the JSON files are empty) to (re)generate these.
