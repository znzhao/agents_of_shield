# Agents of S.H.I.E.L.D. - Interactive Story Viewer

An interactive web application for exploring the TV series "Agents of S.H.I.E.L.D." with AI-powered character interactions, episode analysis, semantic search, and character profiling.

## Features

- **Episode Browser**: Browse all seasons and episodes with detailed scene information
- **Character Profiles**: Comprehensive profiles for characters including demographics, personality, skills, and emotional states
- **AI Chat**: Chat with S.H.I.E.L.D. characters using either OpenAI GPT models or local Ollama models
- **Memory Search**: Search across episodes using semantic similarity or keyword matching
- **Analytics**: Visualize character appearances, locations, and scenes across seasons
- **Parser Control**: Generate and manage character profiles using AI analysis

## Technology Stack

- **Frontend**: Dash (Python web framework) with Dash Bootstrap Components
- **Backend**: Python with LangChain for LLM orchestration
- **LLMs**: OpenAI GPT-4 or Local Ollama models (Qwen)
- **Embeddings**: Sentence Transformers with FAISS for vector search
- **Data**: JSON-based episode and character data
- **Visualization**: Plotly for analytics charts

## Prerequisites

Before you begin, ensure you have:

1. **Python 3.9+** installed
2. **pip** package manager
3. **(Optional) Ollama** for local LLM inference
4. **(Optional) OpenAI API Key** for GPT model access

## Installation & Setup

### 1. Clone or Download the Project

```bash
cd agents_of_shield
```

### 2. Create a Virtual Environment (Recommended)

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root directory:

```bash
# Windows
echo. > .env

# macOS/Linux
touch .env
```

Add the following configuration to `.env`:

```
# OpenAI Configuration (Optional)
OPENAI_API_KEY=sk-your-api-key-here
```

### 5. Get an OpenAI API Key (Optional)

If you want to use GPT models (gpt-4o, gpt-4.1, etc.):

1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in to your account
3. Navigate to **API keys** section
4. Click **Create new secret key**
5. Copy the key and add it to your `.env` file:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```

**Note**: You can use the application without an OpenAI key - it will work with local Ollama models only.

### 6. Set Up Ollama (Optional for Local LLM Inference)

If you want to use local LLMs without paying for OpenAI:

1. **Install Ollama**:
   - Download from [ollama.ai](https://ollama.ai)
   - Follow the installation instructions for your OS

2. **Pull a Model**:
   ```bash
   ollama pull qwen2.5:latest
   ```

3. **Start Ollama Service**:
   ```bash
   ollama serve
   ```

   The service will run on `http://localhost:11434` by default.

4. **Available Models**:
   - `qwen2.5:latest` - Recommended for balanced performance
   - `qwen3:4B` - Lightweight model
   - `qwen3:8B` - More capable model

## Running the Application

### Start the Web Application

```bash
python main.py
```

The application will start and display:
```
Running on http://127.0.0.1:8050
```

Open your browser and navigate to `http://localhost:8050`

### First Launch Setup

On first launch, you'll see a modal asking for your OpenAI API key:
- **Save & Enable GPT**: Enter your API key to access GPT models
- **Proceed Without GPT**: Skip setup to use only local Ollama models

## Using Each Page

### 1. **Home Page**
- View all seasons and episodes in an organized card layout
- Click on any episode to view detailed information
- Browse episode structure with scene-by-scene breakdown
- Default landing page when you start the application

### 2. **Memory Search**
**Purpose**: Find specific scenes, dialogue, or events across episodes

**How to Use**:
1. Enter search keywords (e.g., "betrayal", "mission") in the search box
2. Optionally filter by:
   - **Character**: Select specific character(s) to search within their scenes
   - **Season/Episode Range**: Narrow down search to specific episodes
   - **Search Type**: Toggle between keyword search and semantic similarity search
3. Click **Search** to execute
4. Results show matching scenes with episode info and context
5. Click on any result to navigate to that episode

**Search Types**:
- **Keyword Search**: Exact text matching - faster, precise
- **Semantic Search**: AI-powered similarity - finds contextually related content

### 3. **Analytics Dashboard**
**Purpose**: Visualize and analyze patterns in the series

**How to Use**:
1. Select analysis parameters:
   - **Season**: All seasons or specific season
   - **X-Axis**: Role, Location, or Timestamp
   - **Y-Axis**: Scenes or Episodes
   - **Minimum Count**: Filter out characters/locations with few appearances
2. View interactive charts:
   - **Bar Charts**: Show character appearances, location frequencies
   - **Timeline Charts**: Track development over the series
3. Hover over bars to see exact counts
4. Click and drag to zoom into specific areas
5. Use toolbar to save chart as PNG, reset zoom, etc.

### 4. **Profile Page**
**Purpose**: Explore detailed character information and development arcs

**How to Use**:
1. Select a character from the dropdown menu
2. View comprehensive information organized in tabs:

   **Character Overview Tab**:
   - Basic demographics (age, role, status)
   - Personality traits on scales (-10 to +10)
   - Core emotions and mood indicators
   - Skills and attributes

   **Development Tab**:
   - Character arc over the series
   - Key transformations and moments
   - Timeline of significant events

   **Appearance Timeline Tab**:
   - Which seasons and episodes the character appears in
   - Scene counts by season
   - Visual timeline of character presence

3. Color coding helps visualize traits:
   - Red/Orange: Negative values, tension
   - White: Neutral
   - Green/Blue: Positive values, harmony

**Profile Features**:
- Traits include: Loyalty, Intelligence, Humor, Aggression, Courage, etc.
- Emotional states updated throughout the series based on events
- Skills tracked: Combat, Hacking, Leadership, Problem-solving, etc.

### 5. **Chat With**
**Purpose**: Have interactive conversations with S.H.I.E.L.D. characters

**How to Use**:
1. **Select Character**: Choose from the character dropdown
2. **Select Model**: Pick your LLM:
   - **GPT-4o** (Requires OpenAI key) - Most capable
   - **GPT-4.1** (Requires OpenAI key) - Advanced reasoning
   - **GPT-4.1 Mini** (Requires OpenAI key) - Balanced performance/cost
   - **Qwen2.5:latest** - Local, free, good quality
   - **Qwen3:4B** - Local, lightweight
   - **Qwen3:8B** - Local, more capable

3. **Configure Settings**:
   - **Temperature**: 0 (deterministic) to 2 (creative)
     - Use 0-0.5 for factual conversations
     - Use 0.7-1.5 for creative/roleplay conversations
   - **Max Tokens**: Limit response length (higher = longer responses)

4. **Start Chatting**:
   - Type your message in the input box
   - Press Enter or click Send
   - Wait for the character to respond
   - Chat history is displayed above

5. **Tips**:
   - Ask about character relationships and backstory
   - Request advice "in character"
   - Ask about specific episodes or events
   - Character personality is based on their profile data

**Conversation Context**:
- The character has knowledge of events from the series
- Responses are influenced by character personality and relationships
- The AI tries to stay in character based on the character profile

### 6. **Parser Control**
**Purpose**: Generate and update AI-powered character profiles

**How to Use** (Advanced Feature):
1. **Select Target**:
   - Choose Season
   - Choose Episode
   - Choose Character/Role ID

2. **View Episode Info**:
   - Scene count and character appearances
   - Basic episode metadata

3. **Configure Processing**:
   - Select Model (GPT recommended for quality)
   - Adjust temperature if needed

4. **Run Parser**:
   - Click **Run Parser** button
   - Progress indicator shows processing status
   - Wait for completion

5. **Review Results**:
   - Once complete, see updated character profile
   - Profile includes new personality assessments
   - Check for accuracy and adjust if needed

**Note**: This feature requires significant processing time and API calls if using GPT. Start with Ollama models for testing.

## Project Structure

```
agents_of_shield/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create this)
├── README.md              # This file
├── core/                  # Core utilities
│   ├── llm_engine.py     # LLM interface (OpenAI & Ollama)
│   └── utils.py          # Helper functions
├── pages/                 # Web pages
│   ├── home.py           # Episode browser
│   ├── episode.py        # Episode detail view
│   ├── analytics.py      # Analytics dashboard
│   ├── profile.py        # Character profiles
│   ├── chat_with.py      # Character chat interface
│   ├── memory_search.py  # Episode search
│   └── parser_control.py # Profile generation control
├── model_structure/       # Data models
│   ├── embedding.py      # Vector embeddings
│   ├── stories.py        # Episode data structures
│   └── roles.py          # Character data structures
├── utils/                 # Utilities
│   ├── chat_bot.py       # Chat orchestration
│   └── profile_manager.py # Character profile management
├── processors/            # Data processing
│   ├── pov_parser.py     # Scene analysis
│   └── role_profile_parser.py # Character profile generation
├── data_manager/          # Data utilities
│   ├── transcript_downloader.py
│   └── synopsis_downloader.py
├── desk_dash/             # Custom Dash wrapper
├── assets/                # CSS and stylesheets
│   └── chat_with.css
└── data/                  # Series data
    ├── agents_of_shield.json
    └── Season_1/ ... Season_7/
        └── Episodes with transcripts, synopses, etc.
```

## Troubleshooting

### Ollama Connection Issues
```
Error: Failed to connect to Ollama
Solution: Ensure Ollama is running with `ollama serve` in another terminal
```

### OpenAI API Key Not Working
```
Error: Invalid API key
Solution: 
1. Verify key starts with 'sk-'
2. Check it has not expired in OpenAI dashboard
3. Ensure you have API credits available
```

### Memory/Performance Issues
```
If the app is slow or freezes:
1. Close unnecessary browser tabs
2. Reduce embedding search scope (fewer seasons/episodes)
3. Use lighter Ollama model (qwen2.5:latest)
4. Restart the application
```

### Models Not Appearing
```
For GPT models:
- Ensure OPENAI_API_KEY is set in .env
- Verify key has proper permissions in OpenAI dashboard

For Ollama models:
- Run `ollama pull qwen2.5:latest`
- Start Ollama service: `ollama serve`
- Check http://localhost:11434 is accessible
```

## Performance Tips

1. **First Load**: Initial episode loading may take time as embeddings are created
2. **Semantic Search**: Slower but more accurate - good for finding related concepts
3. **Keyword Search**: Faster for exact phrase matching
4. **Character Profiles**: Generated once and cached - reuse them!
5. **Model Selection**: Ollama models are free but slower; GPT is faster but costs money

## Development & Customization

### Adding New Characters
Characters are defined in `data/agents_of_shield.json`. Edit the file to add new roles.

### Customizing Themes
Color themes are defined in each page file (look for `THEME` dictionary). Modify RGB values to customize colors.

### Integrating New Data
Ensure data follows the structure in `model_structure/stories.py` and `model_structure/roles.py`

## License

This project is for educational and entertainment purposes.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Verify all dependencies are installed: `pip list | findstr dash plotly langchain openai`
3. Check that .env file is properly configured
4. Review application logs in the console

## Contributors

Built with Python, Dash, LangChain, and OpenAI technologies.
