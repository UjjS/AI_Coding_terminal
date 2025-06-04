const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

let snake = [{ x: 200, y: 200 }];
let direction = { x: 20, y: 0 };
let food = { x: randomCoordinate(), y: randomCoordinate() };

function randomCoordinate() {
    return Math.floor(Math.random() * 20) * 20;
}

function drawSnakePart(snakePart) {
    ctx.fillStyle = 'green';
    ctx.fillRect(snakePart.x, snakePart.y, 20, 20);
    ctx.strokeRect(snakePart.x, snakePart.y, 20, 20);
}

function drawSnake() {
    snake.forEach(drawSnakePart);
}

function drawFood() {
    ctx.fillStyle = 'red';
    ctx.fillRect(food.x, food.y, 20, 20);
}

function moveSnake() {
    const head = { x: snake[0].x + direction.x, y: snake[0].y + direction.y };
    snake.unshift(head);

    if (head.x === food.x && head.y === food.y) {
        food = { x: randomCoordinate(), y: randomCoordinate() };
    } else {
        snake.pop();
    }
}

function changeDirection(event) {
    const keyPressed = event.keyCode;
    const LEFT = 37;
    const UP = 38;
    const RIGHT = 39;
    const DOWN = 40;

    if (keyPressed === LEFT && direction.x === 0) {
        direction = { x: -20, y: 0 };
    }
    if (keyPressed === UP && direction.y === 0) {
        direction = { x: 0, y: -20 };
    }
    if (keyPressed === RIGHT && direction.x === 0) {
        direction = { x: 20, y: 0 };
    }
    if (keyPressed === DOWN && direction.y === 0) {
        direction = { x: 0, y: 20 };
    }
}

document.addEventListener('keydown', changeDirection);

function gameLoop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    moveSnake();
    drawSnake();
    drawFood();
    setTimeout(gameLoop, 100);
}

gameLoop();