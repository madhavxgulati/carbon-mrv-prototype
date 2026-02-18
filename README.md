# Carbon MRV Backend Prototype
A FastAPI-based backend prototype for a carbon MRV (Monitoring, Reporting, Verification) system designed for enhanced rock weathering projects.

This system ingests farm-level data, processes environmental indicators (NDVI, weather), and exposes API endpoints for project tracking.

## Live Demo

Frontend:
https://carbon-mrv-prototype-1.onrender.com/

Backend API:
https://carbon-mrv-prototype.onrender.com/docs


Tech Stack
- Python (FastAPI)
- Uvicorn
- REST API architecture
- NDVI / environmental data integration
- Node frontend (basic UI layer)

Features
- Farm data ingestion
- Carbon project metadata handling
- API endpoints for MRV data
- Local dev setup with uvicorn

How to Run
# Backend
cd backend
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm start



