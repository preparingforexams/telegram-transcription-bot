resource "telegram_bot_webhook" "bot" {
  url = "https://${var.bot_name}.azurewebsites.net/api/handover?code=${var.function_api_key}"
  # See https://core.telegram.org/bots/api#update
  allowed_updates = ["message"]
}
