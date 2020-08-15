terraform {
  backend "remote" {
    hostname = "app.terraform.io"

    workspaces {
      # TODO: name = "workspacename"
    }
  }
}

variable "cloudflare_token" {}

provider "cloudflare" {
  api_token = var.cloudflare_token
}

variable "aws_region" {
  default = "eu-central-1"
}

provider "aws" {
  profile = "default"
  region  = var.aws_region
}

provider "telegram" {
  bot_token = var.telegram_token
}
