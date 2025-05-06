from pathlib import Path

import pandas as pd


def test_csv_loading():
    # Test with an example CSV that definitely exists
    csv_path = Path("examples/LinearGraph.csv")
    assert csv_path.exists(), f"Test CSV file not found at {csv_path}"
    
    df = pd.read_csv(csv_path)
    assert not df.empty
    assert "Node" in df.columns
    assert "GraphName" in df.columns