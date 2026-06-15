import { Outfit } from "@/lib/types"
import { products } from "./products"

export const outfits: Outfit[] = [
  {
    id: "o001",
    concept_id: "c001",
    concept_seed: "Bad Bunny summer concert outfit",
    product_ids: ["p001", "p002", "p003", "p004"],
    products: ["p001", "p002", "p003", "p004"].map((id) => products[id]),
    collage_url: null,
    spec: {
      layout: [
        { product_id: "p001", x: 5,  y: 10, width: 42, rotation: -3,  z_index: 1 },
        { product_id: "p002", x: 12, y: 45, width: 38, rotation: 2,   z_index: 2 },
        { product_id: "p003", x: 52, y: 8,  width: 22, rotation: 5,   z_index: 3 },
        { product_id: "p004", x: 55, y: 38, width: 28, rotation: -4,  z_index: 2 },
      ],
    },
    created_at: "2025-06-01T12:00:00Z",
    metadata: {},
  },
  {
    id: "o002",
    concept_id: "c001",
    concept_seed: "Bad Bunny summer concert outfit",
    product_ids: ["p001", "p003", "p004"],
    products: ["p001", "p003", "p004"].map((id) => products[id]),
    collage_url: null,
    spec: {
      layout: [
        { product_id: "p001", x: 8,  y: 15, width: 45, rotation: 2,  z_index: 1 },
        { product_id: "p003", x: 50, y: 5,  width: 24, rotation: -6, z_index: 2 },
        { product_id: "p004", x: 53, y: 42, width: 30, rotation: 4,  z_index: 3 },
      ],
    },
    created_at: "2025-06-02T12:00:00Z",
    metadata: {},
  },
  {
    id: "o003",
    concept_id: "c002",
    concept_seed: "Nantucket coastal grandmother workday",
    product_ids: ["p005", "p006", "p007", "p008"],
    products: ["p005", "p006", "p007", "p008"].map((id) => products[id]),
    collage_url: null,
    spec: {
      layout: [
        { product_id: "p005", x: 3,  y: 5,  width: 44, rotation: -2, z_index: 1 },
        { product_id: "p006", x: 10, y: 38, width: 36, rotation: 3,  z_index: 2 },
        { product_id: "p007", x: 48, y: 20, width: 40, rotation: -1, z_index: 1 },
        { product_id: "p008", x: 52, y: 58, width: 30, rotation: 5,  z_index: 3 },
      ],
    },
    created_at: "2025-06-03T12:00:00Z",
    metadata: {},
  },
  {
    id: "o004",
    concept_id: "c003",
    concept_seed: "Dark academia rainy campus",
    product_ids: ["p009", "p010", "p007", "p008"],
    products: ["p009", "p010", "p007", "p008"].map((id) => products[id]),
    collage_url: null,
    spec: {
      layout: [
        { product_id: "p009", x: 4,  y: 8,  width: 46, rotation: -4, z_index: 1 },
        { product_id: "p010", x: 14, y: 44, width: 34, rotation: 2,  z_index: 2 },
        { product_id: "p007", x: 50, y: 15, width: 38, rotation: 3,  z_index: 1 },
        { product_id: "p008", x: 54, y: 55, width: 28, rotation: -3, z_index: 3 },
      ],
    },
    created_at: "2025-06-04T12:00:00Z",
    metadata: {},
  },
]
