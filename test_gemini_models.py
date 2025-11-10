#!/usr/bin/env python3
"""
Quick script to list available Gemini models with your API key.
This helps debug the 404 error by showing which models are actually available.
"""

import os
import sys

try:
    import google.generativeai as genai
except ImportError:
    print("ERROR: google-generativeai package not installed")
    print("Run: pip install google-generativeai")
    sys.exit(1)


def list_available_models():
    """List all available Gemini models."""

    # Get API key from environment or settings
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("ERROR: No API key found!")
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")
        print("Example: export GEMINI_API_KEY='your-key-here'")
        sys.exit(1)

    # Configure API
    genai.configure(api_key=api_key)

    print("=" * 70)
    print("AVAILABLE GEMINI MODELS")
    print("=" * 70)
    print()

    try:
        # List all models
        all_models = list(genai.list_models())

        if not all_models:
            print("No models found! Check your API key.")
            return

        print(f"Total models found: {len(all_models)}\n")

        # Filter models that support generateContent
        content_models = []

        for model in all_models:
            print(f"Model: {model.name}")
            print(f"  Display Name: {model.display_name}")
            print(f"  Description: {model.description}")
            print(f"  Supported Methods: {model.supported_generation_methods}")

            if 'generateContent' in model.supported_generation_methods:
                content_models.append(model.name)
                print("  ✅ Supports generateContent")
            else:
                print("  ❌ Does NOT support generateContent")

            print()

        print("=" * 70)
        print("MODELS THAT SUPPORT generateContent:")
        print("=" * 70)

        if content_models:
            for model_name in content_models:
                # Extract just the model ID (remove "models/" prefix)
                model_id = model_name.replace("models/", "")
                print(f"  • {model_id}")
        else:
            print("  No models support generateContent!")

        print()
        print("=" * 70)
        print("RECOMMENDATION:")
        print("=" * 70)

        if content_models:
            recommended = content_models[0].replace("models/", "")
            print(f"Use this model ID in your config: {recommended}")
        else:
            print("No suitable models found. Check your API key permissions.")

    except Exception as e:
        print(f"ERROR: {e}")
        print("\nThis might mean:")
        print("  1. Invalid API key")
        print("  2. API key doesn't have access to Gemini models")
        print("  3. Network/firewall issues")
        print("  4. Region restrictions (Gemini not available in your country)")


if __name__ == "__main__":
    list_available_models()
