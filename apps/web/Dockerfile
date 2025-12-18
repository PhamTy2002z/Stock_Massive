FROM node:20-alpine

WORKDIR /app

# Install dependencies first (cache optimization)
COPY package.json package-lock.json* ./
RUN npm install

# Copy application code
COPY . .

# Development mode
CMD ["npm", "run", "dev"]
