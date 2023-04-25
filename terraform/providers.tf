terraform {
  backend "s3" {
    bucket = "legacy-terraform-states"
    region = "eu-central-1"
    key    = "trazurebot"
  }

  required_providers {
    telegram = {
      source  = "yi-jiayu/telegram"
      version = "0.3.1"
    }
  }
}

provider "telegram" {
  bot_token = var.telegram_token
}
