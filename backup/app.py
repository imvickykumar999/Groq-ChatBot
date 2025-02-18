from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import faiss
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for Matplotlib
import matplotlib.pyplot as plt
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA
from mpl_toolkits.mplot3d import Axes3D
import os
import json
from groq import Groq

app = Flask(__name__)
SCRAPED_DATA_FILE = "static/scraped_data.json"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# Step 1: Extract URLs from the Sitemap
sitemap_url = 'https://blogforge.pythonanywhere.com/sitemap.xml'

# Step 2: Fetch Meta Descriptions
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

def fetch_meta_descriptions():
    if os.path.exists(SCRAPED_DATA_FILE):
        with open(SCRAPED_DATA_FILE, "r") as file:
            return json.load(file)
    
    response = requests.get(sitemap_url)
    sitemap_xml = response.content
    root = ET.fromstring(sitemap_xml)
    namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = [url.find('ns:loc', namespace).text for url in root.findall('ns:url', namespace)]
    
    data = {}
    for url in urls:
        try:
            page_response = requests.get(url, headers=headers)
            if page_response.status_code == 200:
                soup = BeautifulSoup(page_response.text, 'html.parser')
                blog_details = soup.find(class_="blog-details")
                
                if blog_details:
                    data[url] = blog_details.get_text(strip=True)
                else:
                    description_tag = soup.find('meta', attrs={'name': 'description'})
                    data[url] = description_tag['content'] if description_tag and 'content' in description_tag.attrs else 'No meta description found'
            else:
                data[url] = f'Error: {page_response.status_code}'
                
            print(data[url])
        except Exception as e:
            data[url] = f'Error fetching {url}: {str(e)}'
    
    with open(SCRAPED_DATA_FILE, "w") as file:
        json.dump(data, file)
    
    return data

default_options = list(set(fetch_meta_descriptions().values()))

# Load the embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Function to generate embeddings, find similarity, and plot graph
def generate_graph(question, documents):
    all_texts = [question] + documents
    embeddings = model.encode(all_texts)
    embeddings = np.array(embeddings).astype('float32')

    pca = PCA(n_components=3)
    reduced_embeddings = pca.fit_transform(embeddings)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings[1:])

    query_embedding = np.array([embeddings[0]]).astype('float32')
    distances, indices = index.search(query_embedding, len(documents))
    index_distance_map = {idx: dist for dist, idx in zip(distances[0], indices[0])}
    best_match_index = min(index_distance_map, key=index_distance_map.get)

    fig = plt.figure(figsize=(6, 5))
    ax = fig.add_subplot(111, projection='3d')
    q_x, q_y, q_z = reduced_embeddings[0]
    ax.scatter(q_x, q_y, q_z, color='red', label="Question", s=100)
    ax.text(q_x, q_y, q_z, "Q", fontsize=10, color='black', fontweight='bold')
    
    doc_points = reduced_embeddings[1:]
    for i, (x, y, z) in enumerate(doc_points):
        ax.scatter(x, y, z, color='blue')
        ax.text(x, y, z, f"O{i+1}", fontsize=10)
        line_color = 'green' if i == best_match_index else 'red'
        ax.plot([q_x, x], [q_y, y], [q_z, z], linestyle='--', color=line_color)

    ax.set_title("3D Visualization of Question and Option Embeddings")
    ax.set_xlabel("PCA 1")
    ax.set_ylabel("PCA 2")
    ax.set_zlabel("PCA 3")

    graph_path = "static/graph.png"
    plt.savefig(graph_path)
    plt.close()
    return documents[best_match_index], graph_path

def generate_reply(message_text):
    try:
        completion = client.chat.completions.create(
            model="llama-3.2-1b-preview",
            messages=[{"role": "user", "content": message_text}],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=False,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return "Sorry, I'm having trouble processing your request."

@app.route('/', methods=['GET', 'POST'])
def index():
    correct_answer = None
    graph_url = None
    if request.method == 'POST':
        question = request.form['question']
        correct_answer, graph_url = generate_graph(question, default_options)
        
        prompt = f'{question} \n Write in 50 words short reply based on\n {correct_answer}'
        correct_answer = generate_reply(prompt)
    return render_template('index.html', correct_answer=correct_answer, graph_url=graph_url)

if __name__ == '__main__':
    app.run(debug=True)
