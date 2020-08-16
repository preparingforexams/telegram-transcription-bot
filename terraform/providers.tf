terraform {
  backend "remote" {
    hostname = "app.terraform.io"

    workspaces {
      name = "trazurebot"
    }
  }
}

provider "telegram" {
  bot_token = var.telegram_token
}
