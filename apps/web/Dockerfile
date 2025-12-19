FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Entrypoint script to sync packages on startup
CMD sh -c "npm install && npm run dev"
