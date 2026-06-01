FROM node:22-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Compila el bundle de producción (sin hot-reload)
RUN npm run build

EXPOSE 3000

# Sirve el build optimizado
CMD ["npm", "run", "start"]
