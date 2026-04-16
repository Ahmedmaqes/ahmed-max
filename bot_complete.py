# Complete Crypto Trading Bot Application

## Overview
This trading bot is designed to automate the trading of cryptocurrencies on various exchanges using AI agents, Flask web framework, and a paper trading system for testing.

## Features
- Full trading functionalities including buy, sell, and trade history.
- Flask routes for web interface to monitor trading activity.
- AI agents for decision-making based on market conditions.
- Paper trading system to simulate trading without actual money.

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Ahmedmaqes/ahmed-max.git
   cd ahmed-max
   ```
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python bot_complete.py
   ```

## Flask Routes
- `/`: Home page that shows the current status of the bot.
- `/trade`: Endpoint for executing trades.
- `/history`: View trade history.

## AI Agents
The AI agents utilize machine learning algorithms to predict market movements. You can configure them based on your preferred trading strategy.

## Paper Trading
- The bot can operate in a paper trading mode by setting the `PAPER_TRADING` environment variable to `True`. This allows for realistic simulations without financial risk.

## Usage
Once the bot is running, you can interact with it through the web interface to start live trades or paper trades. Monitor profits, losses, and make adjustments as necessary.

## Contributing
Contributions are welcome! Please submit a pull request for any major changes you wish to propose.

## License
This project is licensed under the MIT License.