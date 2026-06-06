FROM node:22-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ENV NEXT_DISABLE_ESLINT=1
RUN npm run build

EXPOSE 3000

# Sirve el build optimizado
CMD ["npm", "run", "start"]
