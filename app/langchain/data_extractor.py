from pydantic import BaseModel 
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate 
from langchain_openai import ChatOpenAI
from app.config import OPENAI_API_KEY
from typing import List

class Vendor(BaseModel):
    name : str | None
    company : str | None
    services : List[str]
    discription : str | None
    contact : list | None 
    email : List[int] | None 
    addresses : List[str]
    cities: List[str]
    countries : List[str]



def ExtractData(chunks):
    if isinstance(chunks[0],str):
        text = chunks[0]
    else:
        text = "\n".join([chunk.page_content for chunk in chunks])
    # print(text)
    parser = PydanticOutputParser(pydantic_object=Vendor)
    
    format_struct = parser.get_format_instructions()

    template = """ 
    You are an information extractor.
    Extract the following fields from the given text:
    -Name (Person's name )
    -Company (Company name or Buisness name )
    -Services(Services provided by that person or a company)
    -Discription (Important Details related to the Services)
    -Contacts(valid mobile numbers or valid phone numbers or vaild Telephone numbers, dont take the address pincode,sector number and house number)
    -Email (emails)
    -Addresses(Addresses of Location were Service is provided or Locations, take the full address with sector number, house number/shop number, pincode )

    Return output ONLY in JSON matching this schema:
    {format_struct}

    Text to analyze :
    {text}
"""
    prompt = PromptTemplate(template=template,input_variables=["text","format_struct"])

    formatted_prompt = prompt.format(text=text,format_struct=format_struct)
    
    llm = ChatOpenAI(model="qwen-plus-latest",temperature=0,openai_api_key=OPENAI_API_KEY,base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1")

    resp = llm.predict(formatted_prompt)
    
    parsed = parser.parse(resp)
    return parsed
   



