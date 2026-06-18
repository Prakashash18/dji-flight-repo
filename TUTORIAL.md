# 🌊 Launching the DJI Flight Volunteer System: An AI-Guided Tutorial

Welcome! In this tutorial, we will walk you through launching both the **FastAPI Processing Station Dashboard** and the **Expo Mobile Client** in development mode. 

To make this tutorial fully **AI-Native**, every step includes a pre-crafted **AI Pilot Prompt** that you can copy and paste directly into your AI assistant (like Antigravity) to have it perform and verify the step for you!

Let's begin! 🚀

## ⚡ The All-in-One Master Prompt (Launch Everything)

If you want to skip the step-by-step prompts and boot the entire stack in a single command, copy and paste this **Master Prompt** into your AI assistant:

> [!TIP]
> ### 🤖 AI Master Pilot Prompt: Spin Up Stack
> ```text
> Please spin up the entire Drone Beach Litter Volunteer System in development mode:
> 1. Create a `.env` file inside `backend/` with standard credentials placeholder values:
>    - `SUPABASE_URL`
>    - `SUPABASE_KEY`
>    - `HOST` as '127.0.0.1'
>    - `PORT` as '8000'
> 2. Navigate to `backend/`, activate the virtual environment, install requirements from `requirements.txt`, and run `main.py` in the background. Verify it starts successfully.
> 3. Navigate to `mobile/`, run `npm install`, and start the Metro bundler using `npm start -- --tunnel` in the background.
> 4. Run the unit test suite `test_system.py` in the workspace root to verify that everything works correctly.
> 5. Provide a summary of the running backend server URL and Metro bundler status once completed.
> ```

---

## 🛠️ Prerequisites

Before we start, make sure you have the following installed on your machine:
1. **Python 3.9+** (to run the backend YOLO engine)
2. **Node.js (v18+) & npm** (to run the Expo Metro Bundler)
3. **Expo Go** app installed on your physical mobile device.
4. A **Supabase** account/project.

---

## 📍 Step 1: Database & Credentials Configuration

Both applications connect to Supabase to register target coordinates, track mission progress, and sync alerts. We need to define these variables in the backend environment configuration.

> [!NOTE]
> ### 🤖 AI Pilot Prompt: Step 1
> Copy and paste the prompt below to have your AI set up the environment variables:
> ```text
> Create a `.env` file in the `backend/` directory of the workspace. Populate it with the following configuration keys:
> - `SUPABASE_URL`
> - `SUPABASE_KEY`
> - `SEA_LION_API_KEY` (use empty string to default to mock translations)
> - `HOST` (set to 127.0.0.1)
> - `PORT` (set to 8000)
> Verify that the file is created successfully and print its location.
> ```

### Manual Fallback:
Create a `.env` file in the `backend/` folder and paste your credentials:
```env
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-supabase-service-role-or-anon-key"
SEA_LION_API_KEY="" # Leave empty to use local fallback translation dictionaries
HOST="127.0.0.1"
PORT=8000
```

---

## 🧠 Step 2: Spin Up the Processing Station Dashboard

The processing station digests high-definition drone videos, interpolates telemetry CSV logs, runs YOLOv8 detections, and projects coordinate structures.

> [!NOTE]
> ### 🤖 AI Pilot Prompt: Step 2
> Copy and paste the prompt below to have your AI prepare the environment and spin up the server:
> ```text
> Set up the backend environment and start the processing station server:
> 1. Check if a virtual environment (like `venv`) exists inside `backend/` or workspace root and activate it.
> 2. Install all dependencies from `backend/requirements.txt` using pip.
> 3. Start the FastAPI server by running `main.py` in the background.
> 4. Verify the startup logs to ensure both the Supabase client and FastAPI server are running correctly on port 8000.
> ```

### Manual Fallback:
Navigate to the backend, initialize the virtual environment, install requirements, and run the server:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```
Open [http://localhost:8000](http://localhost:8000) in your web browser. You should see the dark obsidian-themed **Scout Command Center Dashboard**.

---

## 📱 Step 3: Launch the Expo Mobile Client

To view the volunteers' mobile screens, compile and start the Expo project using a secure tunnel.

> [!NOTE]
> ### 🤖 AI Pilot Prompt: Step 3
> Copy and paste the prompt below to have your AI bundle and expose the mobile client:
> ```text
> Configure and spin up the mobile application Metro server:
> 1. Navigate to the `mobile/` directory.
> 2. Run `npm install` to download dependencies.
> 3. Start the Metro bundler using `npm start -- --tunnel`.
> 4. Monitor the task output and notify me when the tunnel link or QR code is ready so I can scan it.
> ```

### Manual Fallback:
Navigate to the mobile directory, install Node modules, and run the tunnel script:
```bash
cd mobile
npm install
npm start -- --tunnel
```
Once the bundler is active, open the **Expo Go** application on your smartphone and scan the QR code displayed in the terminal.

---

## 🧪 Step 4: Validate Custom YOLO Model & Ingestion Pipelines

Before running a real flight test, verify that the backend process endpoint successfully ingests custom weights and logs without errors.

> [!NOTE]
> ### 🤖 AI Pilot Prompt: Step 4
> Copy and paste the prompt below to verify the georeferencing and custom weights upload endpoint:
> ```text
> Run the system tests to verify that custom weights uploads and georeferencing pipelines are fully operational:
> 1. Run the Python unit tests in `test_system.py` inside the workspace root.
> 2. Verify that both the standard tests and the custom model tests (`test_process_endpoint_custom_model` and `test_process_endpoint_custom_model_invalid_extension`) pass.
> 3. Report any failures or resource warnings.
> ```

### Manual Fallback:
Run the unit test suite inside your workspace root:
```bash
python3 -m unittest test_system.py
```
If you see `OK` at the end, all systems are fully synchronized and ready for volunteer testing!

---

## 🚀 Step 5: Run a Test Ingestion Session

Now that both screens are up, let's process a flight log:

1. **Dashboard Upload**: Go to the browser at `http://localhost:8000` (Step 1 of the wizard). Upload a drone flight video (e.g. `.mp4`) and a telemetry CSV log.
2. **Weights Selection**: In Step 2 of the wizard, change the YOLOv8 Detection Weights selection to **Swap out to custom model (.pt)** and upload your custom model weights file.
3. **Ingestion**: Click **Start Georeferencing**.
4. **Real-time Sync**: The map will update dynamically showing the drone's position, and detections will instantly pop up on the mobile app's map for logged-in volunteers.
5. **Session Reset**: Click **Start New Session** to clear all paths, reset the dropdown, and prepare for the next flight.
