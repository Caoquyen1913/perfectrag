FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --prefer-offline --no-audit

FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./
EXPOSE 3001
CMD ["npm", "start"]
