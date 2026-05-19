# ParallelLife

ParallelLife simulates alternate versions of your life based on your inputs and public context signals. It returns alternate timelines, future snapshots, income and lifestyle projections, and a regret probability score.

## Setup

1. Create a virtual environment and install dependencies:

```
pip install -r requirements.txt
```

2. Set environment variables in a `.env` file (optional but recommended):

```
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=sqlite:///./parallel_life.db
```

3. Run the server:

```
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 in the browser.
