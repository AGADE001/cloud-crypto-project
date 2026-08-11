#[Defines terraform version and required provider plugins]
terraform {
    required_version = ">=1.0.0"

    required_providers {
        aws = {
            source  = "hashicorp/aws"
            version = "~> 5.0"
        }
    }
}
#----------------------------------------------------------------------
provider "aws" {
    region = "us-east-1" #Data Centers from northern Virginia
}
#----------------------------------------------------------------------
#[Create the general core network container (VPC)]
resource "aws_vpc" "crypto_network" {
    cidr_block = "10.0.0.0/16" # Provides 65,536 private IP addresses
    enable_dns_hostnames = true #gives resources internal domain names
    enable_dns_support  = true

    tags = {
        Name        = "crypto-project-vpc"
        Environment = "Production"
    }
}
#----------------------------------------------------------------------
#[Create public subnet]
resource "aws_subnet" "public_subnet" {
    vpc_id                  = aws_vpc.crypto_network.id
    cidr_block              = "10.0.1.0/24" # Provides 256 IPs
    availability_zone       = "us-east-1a"
    map_public_ip_on_launch = true

    tags = {
        Name        = "crypto-public-subnet"
        Environment = "Production"
    }
}
#----------------------------------------------------------------------
#[Create private subnet]
resource "aws_subnet" "private_subnet" {
    vpc_id                  = aws_vpc.crypto_network.id
    cidr_block              = "10.0.2.0/24"
    availability_zone       = "us-east-1a"

    tags = {
        Name        = "crypto-private-subnet"
        Environment = "Production"
    }
}
#----------------------------------------------------------------------
#[Creates intneranl gateway(Acts as a Modem)]
resource "aws_internet_gateway" "igw" {
    vpc_id = aws_vpc.crypto_network.id

    tags = {
        Name = "crypto-internal-gateway"
    }
}
#----------------------------------------------------------------------
#[Creates a Route Table for the public subnet]
resource "aws_route_table" "public_route_table" {
    vpc_id = aws_vpc.crypto_network.id

    # Default route: Send all external internet traffic (0.0.0.0/0) to the Internet Gateway
    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = aws_internet_gateway.igw.id
    }

    tags = {
        Name = "crypto-public-route-table"
    }
}
#----------------------------------------------------------------------
#[Links Route table to public subnet]
resource "aws_route_table_association" "public_link" {
    subnet_id      = aws_subnet.public_subnet.id
    route_table_id = aws_route_table.public_route_table.id
}
#----------------------------------------------------------------------
#[Security Group for Internal Database and Cache system]
resource "aws_security_group" "internal_db_sg" {
    name        = "crypto-internal-db-sg"
    description = "Allow internal traffic to Postgres and Redis"
    vpc_id      = aws_vpc.crypto_network.id

    #Inbound rule for PostgreSQL form within vpc
    ingress {
        from_port   = 5432
        to_port     = 5432
        protocol    = "tcp"
        cidr_blocks = [ "10.0.0.0/16" ]
    }
    #Inbound rule for Redis form within vpc
    ingress {
        from_port   = 6379
        to_port     = 6379
        protocol    = "tcp"
        cidr_blocks = [ "10.0.0.0/16" ]
    }
    #Inbound rule for PublicIP form within vpc
    ingress {
        from_port = 22
        to_port = 22
        protocol = "tcp"
        cidr_blocks = [ "0.0.0.0/0" ]
    }
    #outbound rule for required use cases
    egress {
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = [ "0.0.0.0/0" ]
    }

    tags = {
        Name = "crypto-internal-security-group"
    }
}
#----------------------------------------------------------------------
#[Dynamic AMI variable for Virtual Server(EC2)]
data "aws_ami" "ubuntu" { # Fetch the latest official Ubuntu 22.04 LTS AMI dynamically
  most_recent = true
  owners = ["099720109477"] #Canonicals official public vendor id
  
  filter {
    name = "name"
    values = [ "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" ]
  }

  filter {
    name = "virtualization-type"
    values = ["hvm"]
  }
}
#----------------------------------------------------------------------
#[This resource provides public key to access Ubuntu]
resource "aws_key_pair" "deployer" {
  key_name = "crypto-deployer-key"
  public_key = file("~/.ssh/id_rsa.pub")
}
#----------------------------------------------------------------------
#[Defining Virtual Server(EC2) for AWS]
resource "aws_instance" "crypto_engine_server" {
  ami = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  
  subnet_id = aws_subnet.public_subnet.id
  vpc_security_group_ids = [aws_security_group.internal_db_sg.id]
  key_name = aws_key_pair.deployer.key_name
  
  user_data = <<-EOF
              #!/bin/bash
              sudo apt-get update -y
              sudo apt-get install -y docker.io docker.compose
              sudo systemctl start docker
              sudo systemctl enable docker
              EOF
  tags = {
    Name = "crypto-engine-server"
  }
}
#----------------------------------------------------------------------
#[This funtcion makes it accessible publicly]
output "public_ip" {
  description = "The public ip address of the crypto ingestion server"
  value = aws_instance.crypto_engine_server.public_ip
}
