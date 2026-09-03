FROM node:20-alpine

WORKDIR /app

# Capa de dependencias separada para aprovechar la cache de Docker
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
