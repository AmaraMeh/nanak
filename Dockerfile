# Runtime image with Playwright (Chromium) preinstalled
FROM mcr.microsoft.com/playwright:v1.47.2-jammy

WORKDIR /app

COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN npm install --omit=dev && npx playwright install chromium

COPY tsconfig.json ./
COPY src ./src
COPY .env.example ./

RUN npm run build

ENV NODE_ENV=production
CMD ["node", "dist/index.js"]
