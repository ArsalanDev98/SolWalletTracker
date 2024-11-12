import requests
from datetime import datetime

class HeliusTransactionScanner:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = f"https://api.helius.xyz/v0"
        self.token_cache = {}  # Cache for token info

    def get_transactions(self, address, max_transactions=1000):
        """
        Fetch transactions for an address using Helius API
        """
        endpoint = f"{self.base_url}/addresses/{address}/transactions"
        
        params = {
            "api-key": self.api_key,
            "limit": min(100, max_transactions),
            "commitment": "confirmed"
        }

        all_transactions = []
        try:
            while True:
                print(f"Fetching batch of transactions...")
                response = requests.get(endpoint, params=params)
                response.raise_for_status()
                transactions = response.json()
                
                if not transactions:
                    break
                    
                all_transactions.extend(transactions)
                print(f"Found {len(transactions)} transactions in this batch")
                
                if len(all_transactions) >= max_transactions:
                    all_transactions = all_transactions[:max_transactions]
                    break
                
                if len(transactions) == params["limit"]:
                    params["before"] = transactions[-1]["signature"]
                else:
                    break

        except requests.exceptions.RequestException as e:
            print(f"Error fetching transactions: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response content: {e.response.text}")
            return None

        return all_transactions

    def get_token_info(self, mint_address):
        """Fetch token information using Helius API"""
        # Check cache first
        if mint_address in self.token_cache:
            return self.token_cache[mint_address]

        endpoint = f"{self.base_url}/token-metadata"
        params = {
            "api-key": self.api_key
        }
        data = {
            "mintAccounts": [mint_address]
        }
        
        try:
            response = requests.post(endpoint, json=data, params=params)
            response.raise_for_status()
            token_data = response.json()
            if token_data and len(token_data) > 0:
                # Cache the result
                self.token_cache[mint_address] = token_data[0]
                return token_data[0]
        except Exception as e:
            print(f"Error fetching token info for {mint_address}: {e}")
        return None

    def parse_transfer_info(self, tx, address1, address2):
        """Parse transfer information from a Helius transaction"""
        transfers = []

        try:
            # Check native SOL transfers
            if "nativeTransfers" in tx:
                for transfer in tx["nativeTransfers"]:
                    from_address = transfer.get("fromUserAccount")
                    to_address = transfer.get("toUserAccount")
                    amount = transfer.get("amount", 0)

                    if ((from_address == address1 and to_address == address2) or 
                        (from_address == address2 and to_address == address1)):
                        transfers.append({
                            "type": "SOL",
                            "amount": float(amount) / 1e9,
                            "from": from_address,
                            "to": to_address,
                            "timestamp": tx.get("timestamp", 0),
                            "signature": tx.get("signature", "unknown")
                        })

            # Check token transfers
            if "tokenTransfers" in tx:
                for transfer in tx["tokenTransfers"]:
                    from_address = transfer.get("fromUserAccount")
                    to_address = transfer.get("toUserAccount")
                    
                    if ((from_address == address1 and to_address == address2) or 
                        (from_address == address2 and to_address == address1)):
                        amount = float(transfer.get("tokenAmount", 0))
                        decimals = int(transfer.get("decimals", 0))
                        
                        transfers.append({
                            "type": "SPL",
                            "token_name": transfer.get("tokenStandard", "Unknown"),
                            "amount": amount / (10 ** decimals),
                            "from": from_address,
                            "to": to_address,
                            "timestamp": tx.get("timestamp", 0),
                            "signature": tx.get("signature", "unknown")
                        })

        except Exception as e:
            print(f"Error parsing transaction {tx.get('signature', 'unknown')}: {e}")

        return transfers

    def scan_transactions(self, address1, address2, max_transactions=1000):
        """Scan historical transactions between two addresses"""
        print(f"Scanning transactions between:")
        print(f"Address 1: {address1}")
        print(f"Address 2: {address2}")
        print(f"Maximum transactions per address: {max_transactions}")
        print("-" * 50)

        # Get transactions for both addresses
        all_transfers = []
        seen_signatures = set()
        
        for address in [address1, address2]:
            print(f"\nFetching transactions for {address}...")
            transactions = self.get_transactions(address, max_transactions)
            
            if transactions:
                for tx in transactions:
                    if tx['signature'] not in seen_signatures:
                        seen_signatures.add(tx['signature'])
                        transfers = self.parse_transfer_info(tx, address1, address2)
                        for transfer in transfers:
                            if transfer not in all_transfers:  # Avoid duplicates
                                all_transfers.append(transfer)

        # Sort transfers by timestamp
        all_transfers.sort(key=lambda x: x['timestamp'], reverse=True)

        # Track statistics
        transfer_stats = {
            "SOL": {"count": 0, "volume": 0},
            "SPL": {}
        }

        # Process and display transfers
        print(f"\nFound {len(all_transfers)} transfers between addresses:")
        print("-" * 50)

        for i, transfer in enumerate(all_transfers, 1):
            timestamp = datetime.fromtimestamp(transfer['timestamp'])
            
            print(f"\nTransfer {i}:")
            print(f"Date: {timestamp}")
            print(f"Type: {transfer['type']}")
            print(f"Amount: {transfer['amount']}")
            print(f"From: {transfer['from']}")
            print(f"To: {transfer['to']}")
            print(f"Signature: {transfer['signature']}")
            
            # Update statistics
            if transfer['type'] == 'SOL':
                transfer_stats['SOL']['count'] += 1
                transfer_stats['SOL']['volume'] += transfer['amount']
            else:
                token_name = transfer.get('token_name', 'Unknown')
                if token_name not in transfer_stats['SPL']:
                    transfer_stats['SPL'][token_name] = {
                        "count": 0,
                        "volume": 0
                    }
                transfer_stats['SPL'][token_name]['count'] += 1
                transfer_stats['SPL'][token_name]['volume'] += transfer['amount']
            
            print("-" * 50)

        # Print summary
        print("\nTransaction Summary:")
        print(f"SOL Transfers:")
        print(f"  Count: {transfer_stats['SOL']['count']}")
        print(f"  Volume: {transfer_stats['SOL']['volume']:.4f} SOL")
        
        if transfer_stats['SPL']:
            print("\nSPL Token Transfers:")
            for token_name, stats in transfer_stats['SPL'].items():
                print(f"\n{token_name}:")
                print(f"  Count: {stats['count']}")
                print(f"  Volume: {stats['volume']:.4f}")

# Usage
if __name__ == "__main__":
    HELIUS_API_KEY = "80225cdb-a2fb-4173-8b38-22bb29049071"
    
    wallet1 = "7C3o6iK4sNfB2ewc2ExRVPjRttQVBXdMZKXy6u6bh3DF"
    wallet2 = "H5kdkDUfT5umYbRxFKpWkgveeNWf1EcqUgBT7EdRmeij"
    
    max_transactions_per_address = 1000  # Change this number as needed
    
    scanner = HeliusTransactionScanner(HELIUS_API_KEY)
    scanner.scan_transactions(wallet1, wallet2, max_transactions_per_address)