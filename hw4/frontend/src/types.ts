export interface StockLevel {
  size: string;
  quantity: number;
}

export interface ProductMatch {
  product_id: string;
  name: string;
  garment_type: string;
  description: string;
  price: number;
  image_url: string;
  colors: string[];
  stock: StockLevel[];
  total_stock: number;
}

export interface Product extends ProductMatch {
  search_tags: string[];
  image_file_path: string;
}

export interface ChatResponse {
  reply: string;
  matches: ProductMatch[];
}

export interface ChatHistoryMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  matches: ProductMatch[];
  created_at: string;
}

export interface ChatHistoryResponse {
  messages: ChatHistoryMessage[];
}
