#!/usr/bin/env python3
"""Inspects available models on Groq API endpoint and recommends cross-model pairings."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from specoracle.config import load_config

def main():
    config = load_config()
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[!] GROQ_API_KEY environment variable not found.")
        print("    Please set GROQ_API_KEY in your .env file or environment.")
        print("    Displaying default recommended configuration:")
        print(f"    Writer Model:    {config.models_writer}")
        print(f"    Reference Model: {config.models_reference}")
        print(f"    Same Model:      {config.models_same}")
        return

    try:
        from openai import OpenAI
        client = OpenAI(base_url=config.base_url, api_key=api_key)
        models = client.models.list()
        model_ids = sorted([m.id for m in models.data])
        
        print("=== Available Groq Models ===")
        for mid in model_ids:
            print(f" - {mid}")
        
        print("\n=== Recommended SpecOracle Cross-Model Pairs ===")
        print(f"  Test Writer Agent:    {config.models_writer}")
        print(f"  Reference Agent:      {config.models_reference}")
        print("  (Using two distinct model architectures ensures consensus independence)")
    except Exception as e:
        print(f"[x] Error querying Groq API: {str(e)}")

if __name__ == "__main__":
    main()
